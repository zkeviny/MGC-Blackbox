# MirginCipher User Notice

MirginCipher Blackbox (MGC) provides a local encrypted execution environment
designed to protect sensitive human intent and enable secure, efficient AI execution.

This document describes the operational boundaries and safety properties of MGC.

## Encrypted Storage and Execution

- Once plaintext (information, scripts, prompts) is stored inside MGC, it becomes fully
  managed by the Blackbox and cannot be directly viewed or exported.
- All execution occurs within the encrypted boundary and follows deterministic behavior.

## Credential Handling

- During initialization, all related credentials and temporary plaintext materials
  are automatically destroyed.
- MGC does not retain or expose plaintext outside the encrypted boundary.

## Uninstallation and Data Persistence

- Uninstalling MGC removes the program only.
- Encrypted data remains on the device and can be reused after reinstalling.

## Permanent Data Removal

- To permanently erase all data, manually delete the related encrypted storage files.
- After deletion and reinstalling, previously stored information cannot be recovered.

## Acceptance

Use of MGC indicates that you understand and accept the operational boundaries
and irreversible behaviors described in this notice.
