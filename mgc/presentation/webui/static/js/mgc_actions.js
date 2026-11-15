/**
 * MGC Blackbox WebUI - Shared Actions Library
 * Provides reusable button handlers and modal logic for get.html and get_info.html.
 * Dependencies (must exist on the host page):
 *   - window.MGC_TOKEN: API auth token
 *   - waitForToken(): token-ready awaiter (host page defines)
 *   - DOM elements: argsModal, sealModal, resultModal (when respective button used)
 */

(function() {
    'use strict';

    // ---------- Generic modal (resultModal) ----------
    function showModal(title, message) {
        document.getElementById('modalTitle').textContent = title;
        document.getElementById('modalMessage').textContent = message;
        document.getElementById('resultModal').classList.add('show');
    }

    function closeModal() {
        document.getElementById('resultModal').classList.remove('show');
    }

    // ---------- Run script (with optional ext02 override) ----------
    // 1.5.1 phase4 修复：传 diff_1/2/3 保证后端精确匹配，避免多个 record 同 owner 时取错脚本
    async function runScript(infoOwner, diff1, diff2, diff3, ext01, ext02) {
        console.log('runScript called, infoOwner:', infoOwner, 'diff1:', diff1, 'diff2:', diff2, 'diff3:', diff3, 'ext01:', ext01, 'ext02:', ext02);
        await waitForToken();
        const owner = decodeURIComponent(infoOwner);
        const body = {
            info_type: 'script',
            info_owner: owner,
            action: 'run'
        };
        // 1.5.1 phase4 修复：传 diff 字段确保后端 _sensitive_get SQL 精确匹配
        if (diff1) body.diff_1 = decodeURIComponent(diff1);
        if (diff2) body.diff_2 = decodeURIComponent(diff2);
        if (diff3) body.diff_3 = decodeURIComponent(diff3);
        if (ext02) {
            body.ext01 = decodeURIComponent(ext01);
            body.ext02 = decodeURIComponent(ext02);
        }
        try {
            const response = await fetch('/api/mgc/proxy/get', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-MGC-Token': window.MGC_TOKEN || ''
                },
                body: JSON.stringify(body)
            });
            const result = await response.json();
            if (result.code === 200) {
                showModal('Script Running', `Status: ${result.data.status}\nPID: ${result.data.pid || 'N/A'}`);
            } else {
                showModal('Error', result.msg || 'Script execution failed');
            }
        } catch (error) {
            console.error('Script run failed:', error);
            showModal('Error', 'Failed to run script: ' + (error.message || 'Connection failed'));
        }
    }

    function runScriptFromBtn(btn) {
        // 1.5.1 phase4 修复：传 btn.dataset.diff1/2/3
        runScript(
            btn.dataset.owner,
            btn.dataset.diff1,
            btn.dataset.diff2,
            btn.dataset.diff3,
            btn.dataset.ext01,
            btn.dataset.ext02 || ''
        );
    }

    function runScriptWithArgsFromBtn(btn) {
        // 1.5.1 phase4 修复：传 btn.dataset.diff1/2/3
        showArgsModal(
            btn.dataset.owner,
            btn.dataset.diff1,
            btn.dataset.diff2,
            btn.dataset.diff3,
            btn.dataset.ext01,
            btn.dataset.ext02
        );
    }

    // ---------- Args modal (JSON list editor) ----------
    // 1.5.1 phase4 修复：showArgsModal 透传 diff 字段
    function showArgsModal(infoOwner, diff1, diff2, diff3, ext01, ext02) {
        const rawExt02 = decodeURIComponent(ext02 || '');
        const input = document.getElementById('argsInput');
        if (rawExt02) {
            try {
                const parsed = JSON.parse(rawExt02);
                if (Array.isArray(parsed)) {
                    input.value = JSON.stringify(parsed, null, 2);
                } else {
                    input.value = rawExt02;
                }
            } catch (e) {
                input.value = rawExt02;
            }
        } else {
            input.value = '[]';
        }
        const modal = document.getElementById('argsModal');
        modal.dataset.owner = infoOwner;
        modal.dataset.diff1 = diff1 || '';
        modal.dataset.diff2 = diff2 || '';
        modal.dataset.diff3 = diff3 || '';
        modal.dataset.ext01 = ext01;
        modal.classList.add('show');
    }

    function closeArgsModal() {
        document.getElementById('argsModal').classList.remove('show');
    }

    function confirmRunWithArgs() {
        const modal = document.getElementById('argsModal');
        const rawText = document.getElementById('argsInput').value.trim();
        let ext02Str;
        let isLegacyString = false;
        if (!rawText) {
            ext02Str = '[]';
        } else {
            try {
                const parsed = JSON.parse(rawText);
                if (!Array.isArray(parsed) || !parsed.every(item => typeof item === 'string')) {
                    showModal('Error', 'ext02 must be a JSON array of strings, e.g. ["--flag", "value"]');
                    return;
                }
                ext02Str = JSON.stringify(parsed);
            } catch (e) {
                // v1.4.10: legacy 字符串 ext02 (1.4.9/1.4.10-pre) 允许走 split 分支（兼容历史脚本）
                isLegacyString = true;
                ext02Str = rawText;
            }
        }
        // 1.5.1 phase4 修复：透传 modal.dataset.diff1/2/3
        runScript(
            modal.dataset.owner,
            modal.dataset.diff1,
            modal.dataset.diff2,
            modal.dataset.diff3,
            modal.dataset.ext01,
            encodeURIComponent(ext02Str)
        );
        closeArgsModal();
        if (isLegacyString) {
            // v1.4.10: 提示用户升级到 JSON 数组格式（重新存入脚本即可）
            setTimeout(function() {
                showModal(
                    'Legacy ext02 Format Detected',
                    'MGC has detected a legacy ext02 string for this script and used split() fallback at runtime.\n\nRe-saving the script will auto-upgrade ext02 to the structured argv list format (recommended).'
                );
            }, 300);
        }
    }

    // ---------- Seal modal ----------
    function sealScriptFromBtn(btn) {
        console.log('sealScriptFromBtn called, owner:', btn.dataset.owner, 'ext01:', btn.dataset.ext01, 'type:', btn.dataset.type);
        window.pendingSealBtn = btn;
        document.getElementById('sealNodePub').value = '';
        document.getElementById('sealModal').classList.add('show');
    }

    function closeSealModal() {
        document.getElementById('sealModal').classList.remove('show');
        window.pendingSealBtn = null;
    }

    async function confirmSeal() {
        const nodePub = document.getElementById('sealNodePub').value.trim();
        // nodePub is optional — leaving it empty selects free mode at the backend.
        const btn = window.pendingSealBtn;
        if (!btn) {
            showModal('Error', 'No script selected');
            return;
        }
        const owner = decodeURIComponent(btn.dataset.owner);
        closeSealModal();
        showModal('Sealing', 'Sealing script...');
        await new Promise(r => setTimeout(r, 500));
        await sealScript(owner, btn.dataset.type, nodePub);
    }

    async function sealScript(infoOwner, infoType, nodePubKey) {
        console.log('sealScript called, infoOwner:', infoOwner, 'infoType:', infoType, 'nodePubKey:', nodePubKey ? '(provided)' : 'MISSING');
        await waitForToken();
        const owner = decodeURIComponent(infoOwner);
        try {
            const response = await fetch('/api/mgc/proxy/get', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-MGC-Token': window.MGC_TOKEN || ''
                },
                body: JSON.stringify({
                    info_type: 'script',
                    info_owner: owner,
                    action: 'SEAL',
                    ext04: nodePubKey
                })
            });

            if (!response.ok) {
                showModal('Error', 'HTTP error: ' + response.status);
                return;
            }

            const result = await response.json();
            if (result.code === 200 && result.data) {
                // 1.5.4 phase6：胶囊是自描述的——identity 三元组 + 全 ext + 密文，
                // 整段序列化即可。WebUI 不落盘（浏览器下载目录由浏览器决定），
                // 也不再有 get_sealed_info 中转页。
                const sealed = result.data;
                const capsule = {content: sealed.content || ''};
                ['info_type', 'info_owner', 'diff_1', 'diff_2', 'diff_3'].forEach(k => {
                    if (sealed[k] !== undefined) capsule[k] = sealed[k];
                });
                for (let i = 1; i <= 30; i++) {
                    const key = 'ext' + String(i).padStart(2, '0');
                    if (sealed[key] !== undefined) capsule[key] = sealed[key];
                }
                showSealDownloadModal(capsule);
            } else {
                showModal('Error', result.msg || result.hint || 'Seal failed');
            }
        } catch (error) {
            console.error('Seal failed:', error);
            showModal('Error', 'Failed to seal script: ' + (error.message || 'Connection failed'));
        }
    }

    // ---------- Seal result: download only ----------

    // Browsers block silent downloads, so the capsule is offered as an explicit
    // Download button inside the success modal instead of navigating anywhere.
    // After the download fires the modal switches to a "downloaded" state that
    // only offers OK, so the user always sees confirmation before dismissing.
    function showSealDownloadModal(capsule) {
        const json = JSON.stringify(capsule, null, 2);
        const owner = capsule.info_owner || 'sealed_script';
        const mode = capsule.ext09 === 'p2p mode' ? 'p2p' : 'free';
        const filename = 'sealed_' + sanitizeFilename(owner) + '_' + mode + '.json';

        const modal = document.getElementById('sealResultModal');
        const holder = document.getElementById('sealResultBody');
        if (modal && holder) {
            const dl = document.getElementById('sealResultDownload');
            const closeBtn = document.getElementById('sealResultClose');
            const okBtn = document.getElementById('sealResultOk');

            const showDownloadState = function () {
                holder.innerHTML =
                    '<p style="margin:0 0 10px 0;">Sealed capsule for <strong>' +
                    escapeHtmlText(owner) + '</strong> (' + mode + ' mode).</p>' +
                    '<p style="margin:0 0 10px 0; color:#666; font-size:13px;">' +
                    'Save it, then paste the JSON into the Save page on the target MGC node ' +
                    '&mdash; every field is auto-detected. Storing it under the same ' +
                    'info_owner on this node overwrites the source record.</p>';
                if (dl) dl.style.display = '';
                if (closeBtn) closeBtn.style.display = 'none';
                if (okBtn) okBtn.style.display = 'none';
            };

            const showDownloadedState = function () {
                holder.innerHTML =
                    '<p style="margin:0 0 10px 0;"><strong>Download started.</strong></p>' +
                    '<p style="margin:0 0 10px 0; color:#666; font-size:13px;">' +
                    'Check your browser download tool for <code>' +
                    escapeHtmlText(filename) + '</code>, then paste its JSON into the ' +
                    'Save page on the target MGC node.</p>';
                if (dl) dl.style.display = 'none';
                if (closeBtn) closeBtn.style.display = 'none';
                if (okBtn) okBtn.style.display = '';
            };

            if (dl) {
                dl.onclick = function () {
                    const blob = new Blob([json], {type: 'application/json'});
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                    showDownloadedState();
                };
            }
            if (closeBtn) closeBtn.onclick = function () { modal.style.display = 'none'; };
            if (okBtn) okBtn.onclick = function () { modal.style.display = 'none'; };
            showDownloadState();
            // Sealing 用的是通用 resultModal，它没有自己的关闭入口；
            // 胶囊弹框接管后顺手关掉，避免用户看到两层弹框叠在一起。
            closeModal();
            modal.style.display = 'flex';
            return;
        }

        // Fallback: no dedicated modal in this template.
        showModal('Success', 'Script sealed. Use the Get page again if you need to download it.');
    }

    function sanitizeFilename(name) {
        return String(name || 'sealed_script')
            .replace(/[<>:"/\\|?*\x00-\x1f]/g, '_')
            .slice(0, 64) || 'sealed_script';
    }

    function escapeHtmlText(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    // ---------- Navigate to detail page ----------
    function getInfoFromBtn(btn) {
        const params = {
            info_type: decodeURIComponent(btn.dataset.type),
            info_owner: decodeURIComponent(btn.dataset.owner)
        };
        if (btn.dataset.diff1) params.diff_1 = decodeURIComponent(btn.dataset.diff1);
        if (btn.dataset.diff2) params.diff_2 = decodeURIComponent(btn.dataset.diff2);
        if (btn.dataset.diff3) params.diff_3 = decodeURIComponent(btn.dataset.diff3);

        localStorage.setItem('mgc_get_params', JSON.stringify(params));
        location.href = '/get_info';
    }

    // ---------- Delete ----------
    async function deleteInfoFromBtn(btn) {
        const infoOwner = btn.dataset.owner;
        const infoType = btn.dataset.type;
        const diff1 = btn.dataset.diff1 || '';
        const diff2 = btn.dataset.diff2 || '';
        const diff3 = btn.dataset.diff3 || '';

        if (!confirm('Delete cannot be undone. The information will be permanently deleted.\n\nAre you sure you want to delete "' + decodeURIComponent(infoOwner) + '"?')) {
            return;
        }

        btn.disabled = true;
        let countdown = 3;
        btn.textContent = `Deleting... ${countdown}`;

        const countdownInterval = setInterval(() => {
            countdown--;
            if (countdown > 0) {
                btn.textContent = `Deleting... ${countdown}`;
            }
        }, 1000);

        try {
            const response = await fetch('/api/mgc/proxy/delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-MGC-Token': window.MGC_TOKEN || ''
                },
                body: JSON.stringify({
                    info_type: decodeURIComponent(infoType),
                    info_owner: decodeURIComponent(infoOwner),
                    diff_1: decodeURIComponent(diff1) || null,
                    diff_2: decodeURIComponent(diff2) || null,
                    diff_3: decodeURIComponent(diff3) || null
                })
            });

            clearInterval(countdownInterval);

            const result = await response.json();

            if (response.ok && (result.code === 0 || result.code === 200)) {
                alert('Deleted successfully!');
                // 1.5.1 phase7: get 页改名为 list；get_info 跳 list 页，list 页 reload 自己
                if (location.pathname === '/get_info') {
                    location.href = '/list';
                } else {
                    location.reload();
                }
            } else {
                alert('Delete failed: ' + (result.msg || 'Unknown error'));
                btn.disabled = false;
                btn.textContent = 'Delete';
            }
        } catch (error) {
            clearInterval(countdownInterval);
            alert('Delete failed: ' + (error.message || 'Connection failed'));
            btn.disabled = false;
            btn.textContent = 'Delete';
        }
    }

    // ---------- Folder Delete (1.5.1 phase7) ----------
    // 1.5.1 phase7: folder 级批量删除
    // - 按 (info_owner + diff_2) 删除整个 folder 下所有内容
    // - 不传 diff_1 / diff_3（避免误删其他 folder 内的精确记录）
    // - 后端 SQL 已对齐过滤模式（database_handler.delete_sensitive_info 透传 diff_1/2/3）
    // - 用户接受"误触风险"（PM 决策：不二次校验）
    async function deleteFolderFromBtn(btn) {
        const infoOwner = btn.dataset.owner;
        const diff2 = btn.dataset.diff2 || '';

        if (!confirm('Delete Folder cannot be undone. All records in folder "' + decodeURIComponent(infoOwner) + ' / ' + decodeURIComponent(diff2) + '" will be permanently deleted.\n\nAre you sure?')) {
            return;
        }

        btn.disabled = true;
        btn.textContent = 'Deleting...';

        try {
            // 1.5.1 phase7: 不传 info_type（folder 下混有 text/script/file，不加 info_type 过滤）
            const response = await fetch('/api/mgc/proxy/delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-MGC-Token': window.MGC_TOKEN || ''
                },
                body: JSON.stringify({
                    info_type: '',
                    info_owner: decodeURIComponent(infoOwner),
                    diff_1: '',
                    diff_2: decodeURIComponent(diff2),
                    diff_3: ''
                })
            });

            const result = await response.json();

            if (response.ok && (result.code === 0 || result.code === 200)) {
                alert('Folder deleted successfully!');
                location.reload();
            } else {
                alert('Folder delete failed: ' + (result.msg || 'Unknown error'));
                btn.disabled = false;
                btn.textContent = 'Delete Folder';
            }
        } catch (error) {
            alert('Folder delete failed: ' + (error.message || 'Connection failed'));
            btn.disabled = false;
            btn.textContent = 'Delete Folder';
        }
    }

    // ---------- Expose to window ----------
    // Direct bindings so inline onclick handlers can call them as global functions
    window.MGC_Actions = {
        showModal: showModal,
        closeModal: closeModal,
        runScript: runScript,
        runScriptFromBtn: runScriptFromBtn,
        runScriptWithArgsFromBtn: runScriptWithArgsFromBtn,
        showArgsModal: showArgsModal,
        closeArgsModal: closeArgsModal,
        confirmRunWithArgs: confirmRunWithArgs,
        sealScriptFromBtn: sealScriptFromBtn,
        closeSealModal: closeSealModal,
        confirmSeal: confirmSeal,
        sealScript: sealScript,
        getInfoFromBtn: getInfoFromBtn,
        deleteInfoFromBtn: deleteInfoFromBtn,
        // 1.5.1 phase7: folder 级 Delete（按 info_owner + diff_2 批量删除）
        deleteFolderFromBtn: deleteFolderFromBtn
    };
    // Global aliases for inline onclick (e.g., onclick="runScriptFromBtn(this)")
    window.showModal = showModal;
    window.closeModal = closeModal;
    window.runScript = runScript;
    window.runScriptFromBtn = runScriptFromBtn;
    window.runScriptWithArgsFromBtn = runScriptWithArgsFromBtn;
    window.showArgsModal = showArgsModal;
    window.closeArgsModal = closeArgsModal;
    window.confirmRunWithArgs = confirmRunWithArgs;
    window.sealScriptFromBtn = sealScriptFromBtn;
    window.closeSealModal = closeSealModal;
    window.confirmSeal = confirmSeal;
    window.sealScript = sealScript;
    window.getInfoFromBtn = getInfoFromBtn;
    window.deleteInfoFromBtn = deleteInfoFromBtn;
    // 1.5.1 phase7: folder 级 Delete（按 info_owner + diff_2 批量删除）
    window.deleteFolderFromBtn = deleteFolderFromBtn;

    // ============================================================
    // PR-6 (1.5.0 phase2 / 技能授权) — Folder Package Actions
    // ============================================================
    //
    // 触发的 DOM 元素约定（get.html 模板需新增）：
    //   1) "Package" 按钮：onclick="packageFolderFromBtn(this)"
    //      btn.dataset = {owner, diff2, diff1, type="file", outputDir=""}
    //      弹 modal：id="packageFolderModal" 含 outputDir 输入框 id="packageFolderOutputDir"
    //      confirm 调 confirmPackageFolder()
    //
    //   2) "Seal Package" 按钮：onclick="sealPackageFolderFromBtn(this)"
    //      btn.dataset = {owner, diff2, diff1, type="file", outputDir="", nodePub=""}
    //      弹 modal：id="sealPackageFolderModal" 含 input id="sealPackageFolderNodePub" / id="sealPackageFolderOutputDir"
    //      confirm 调 confirmSealPackageFolder()
    //
    // 涉及后端 endpoint（api_router 接入留待 PR-6 收尾 / 端到端联调）：
    //   POST /api/mgc/proxy/get  body: { info_type:"file", info_owner, diff_2, diff_1, action:"package"|"seal_package", output_dir, ext04? }
    //

    function packageFolderFromBtn(btn) {
        try {
            const owner = decodeURIComponent(btn.dataset.owner || '');
            const diff2 = decodeURIComponent(btn.dataset.diff2 || '');
            const diff1 = decodeURIComponent(btn.dataset.diff1 || '');
            // 预填上次用过的输出目录（localStorage）
            const lastOutputDir = localStorage.getItem('mgc_pkg_output_dir') || '';
            const outputDirInput = document.getElementById('packageFolderOutputDir');
            if (outputDirInput) {
                outputDirInput.value = lastOutputDir;
            }
            // 缓存信息到 modal dataset（v1.5.0：B 按钮的 (this) 不是 Package 按钮，
            // 原 btn.dataset.* 在 confirm 阶段会被读到空，改为 modal.dataset.* 修复）
            const modal = document.getElementById('packageFolderModal');
            if (modal) {
                modal.dataset.owner = encodeURIComponent(owner);
                modal.dataset.diff2 = encodeURIComponent(diff2);
                modal.dataset.diff1 = encodeURIComponent(diff1);
                modal.classList.add('show');
            } else {
                console.warn('packageFolderModal not found; falling back to synchronous call');
                return _callPackageFolder(owner, diff2, diff1, lastOutputDir, btn);
            }
        } catch (e) {
            console.error('packageFolderFromBtn failed:', e);
            showModal('Error', 'Failed to open package dialog: ' + (e.message || e));
        }
    }

    function closePackageFolderModal() {
        const modal = document.getElementById('packageFolderModal');
        if (modal) {
            modal.classList.remove('show');
            delete modal.dataset.owner;
            delete modal.dataset.diff2;
            delete modal.dataset.diff1;
        }
    }

    function confirmPackageFolder(btn) {
        try {
            const modal = document.getElementById('packageFolderModal');
            const owner = decodeURIComponent((modal && modal.dataset.owner) || '');
            const diff2 = decodeURIComponent((modal && modal.dataset.diff2) || '');
            const diff1 = decodeURIComponent((modal && modal.dataset.diff1) || '');
            const outputDir = (document.getElementById('packageFolderOutputDir') || {}).value || '';
            if (!outputDir.trim()) {
                showModal('Error', 'output_dir is required');
                return;
            }
            localStorage.setItem('mgc_pkg_output_dir', outputDir);
            closePackageFolderModal();
            return _callPackageFolder(owner, diff2, diff1, outputDir, btn);
        } catch (e) {
            console.error('confirmPackageFolder failed:', e);
            showModal('Error', 'Failed to confirm package: ' + (e.message || e));
        }
    }

    async function _callPackageFolder(infoOwner, diff2, diff1, outputDir, sourceBtn) {
        try {
            if (sourceBtn) { sourceBtn.disabled = true; sourceBtn.textContent = 'Packaging...'; }
            const response = await fetch('/api/mgc/proxy/get', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-MGC-Token': window.MGC_TOKEN || '' },
                body: JSON.stringify({
                    info_type: 'file',
                    info_owner: infoOwner,
                    diff_2: diff2,
                    diff_1: diff1 || '',
                    action: 'package',
                    output_dir: outputDir,
                })
            });
            const result = await response.json();
            if (result && (result.code === 200 || result.msg === 'OPERATION_SUCCESSFUL')) {
                const folderPath = (result.data && (result.data.folder_path || result.data.delivery_path)) || outputDir;
                showModal('Success', 'Folder packaged.\n' + folderPath);
            } else {
                const errCode = (result && (result.data || {}).error) || (result && result.msg) || 'UNKNOWN';
                const hint = (result && result.hint) || '';
                showModal('Error', 'Package failed: ' + errCode + (hint ? ('\n' + hint) : ''));
            }
        } catch (error) {
            console.error('_callPackageFolder failed:', error);
            showModal('Error', 'Package failed: ' + (error.message || 'Connection failed'));
        } finally {
            if (sourceBtn) { sourceBtn.disabled = false; sourceBtn.textContent = 'Package'; }
        }
    }

    function sealPackageFolderFromBtn(btn) {
        try {
            const owner = decodeURIComponent(btn.dataset.owner || '');
            const diff2 = decodeURIComponent(btn.dataset.diff2 || '');
            const diff1 = decodeURIComponent(btn.dataset.diff1 || '');
            const lastNodePub = localStorage.getItem('mgc_pkg_node_pub') || '';
            const lastOutputDir = localStorage.getItem('mgc_pkg_output_dir') || '';
            const nodePubInput = document.getElementById('sealPackageFolderNodePub');
            const outputDirInput = document.getElementById('sealPackageFolderOutputDir');
            if (nodePubInput) nodePubInput.value = lastNodePub;
            if (outputDirInput) outputDirInput.value = lastOutputDir;
            // 缓存信息到 modal dataset（v1.5.0：B 按钮的 (this) 不是 Seal Package 按钮）
            const modal = document.getElementById('sealPackageFolderModal');
            if (modal) {
                modal.dataset.owner = encodeURIComponent(owner);
                modal.dataset.diff2 = encodeURIComponent(diff2);
                modal.dataset.diff1 = encodeURIComponent(diff1);
                modal.classList.add('show');
            } else {
                console.warn('sealPackageFolderModal not found; falling back to synchronous call');
                return _callSealPackageFolder(owner, diff2, diff1, lastNodePub, lastOutputDir, btn);
            }
        } catch (e) {
            console.error('sealPackageFolderFromBtn failed:', e);
            showModal('Error', 'Failed to open seal dialog: ' + (e.message || e));
        }
    }

    function closeSealPackageFolderModal() {
        const modal = document.getElementById('sealPackageFolderModal');
        if (modal) {
            modal.classList.remove('show');
            delete modal.dataset.owner;
            delete modal.dataset.diff2;
            delete modal.dataset.diff1;
        }
    }

    function confirmSealPackageFolder(btn) {
        try {
            const modal = document.getElementById('sealPackageFolderModal');
            const owner = decodeURIComponent((modal && modal.dataset.owner) || '');
            const diff2 = decodeURIComponent((modal && modal.dataset.diff2) || '');
            const diff1 = decodeURIComponent((modal && modal.dataset.diff1) || '');
            const nodePub = ((document.getElementById('sealPackageFolderNodePub') || {}).value || '').trim();
            const outputDir = ((document.getElementById('sealPackageFolderOutputDir') || {}).value || '').trim();
            // nodePub is optional — leaving it empty selects free mode. PEM-format
            // validation only runs when an input is provided.
            if (nodePub && !nodePub.includes('-----BEGIN')) {
                showModal('Error', 'node_pub must be a multi-line PEM format, or leave empty for free mode'); return;
            }
            if (!outputDir) { showModal('Error', 'output_dir is required'); return; }
            localStorage.setItem('mgc_pkg_node_pub', nodePub);
            localStorage.setItem('mgc_pkg_output_dir', outputDir);
            closeSealPackageFolderModal();
            return _callSealPackageFolder(owner, diff2, diff1, nodePub, outputDir, btn);
        } catch (e) {
            console.error('confirmSealPackageFolder failed:', e);
            showModal('Error', 'Failed to confirm seal package: ' + (e.message || e));
        }
    }

    async function _callSealPackageFolder(infoOwner, diff2, diff1, nodePub, outputDir, sourceBtn) {
        try {
            if (sourceBtn) { sourceBtn.disabled = true; sourceBtn.textContent = 'Sealing...'; }
            const response = await fetch('/api/mgc/proxy/get', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-MGC-Token': window.MGC_TOKEN || '' },
                body: JSON.stringify({
                    info_type: 'file',
                    info_owner: infoOwner,
                    diff_2: diff2,
                    diff_1: diff1 || '',
                    action: 'seal_package',
                    ext04: nodePub,
                    output_dir: outputDir,
                })
            });
            const result = await response.json();
            if (result && (result.code === 200 || result.msg === 'OPERATION_SUCCESSFUL')) {
                const deliveryPath = (result.data && result.data.delivery_path) || outputDir;
                const mgcPath = (result.data && result.data.mgc_file_path) || '';
                const readmePath = (result.data && result.data.readme_path) || '';
                showModal('Success', 'Sealed package generated.\n' + deliveryPath +
                    (mgcPath ? ('\n.mgc_file: ' + mgcPath) : '') +
                    (readmePath ? ('\nREADME.md: ' + readmePath) : ''));
            } else {
                const errCode = (result && (result.data || {}).error) || (result && result.msg) || 'UNKNOWN';
                const hint = (result && result.hint) || '';
                showModal('Error', 'Seal package failed: ' + errCode + (hint ? ('\n' + hint) : ''));
            }
        } catch (error) {
            console.error('_callSealPackageFolder failed:', error);
            showModal('Error', 'Seal package failed: ' + (error.message || 'Connection failed'));
        } finally {
            if (sourceBtn) { sourceBtn.disabled = false; sourceBtn.textContent = 'Seal Package'; }
        }
    }

    // PR-6 expose
    window.MGC_Actions.packageFolderFromBtn = packageFolderFromBtn;
    window.MGC_Actions.closePackageFolderModal = closePackageFolderModal;
    window.MGC_Actions.confirmPackageFolder = confirmPackageFolder;
    window.MGC_Actions.sealPackageFolderFromBtn = sealPackageFolderFromBtn;
    window.MGC_Actions.closeSealPackageFolderModal = closeSealPackageFolderModal;
    window.MGC_Actions.confirmSealPackageFolder = confirmSealPackageFolder;
    window.packageFolderFromBtn = packageFolderFromBtn;
    window.closePackageFolderModal = closePackageFolderModal;
    window.confirmPackageFolder = confirmPackageFolder;
    window.sealPackageFolderFromBtn = sealPackageFolderFromBtn;
    window.closeSealPackageFolderModal = closeSealPackageFolderModal;
    window.confirmSealPackageFolder = confirmSealPackageFolder;
})();