#!/usr/bin/env python3
import os
import subprocess
import shutil

FSTAB_PATH = "/etc/fstab"
BACKUP_PATH = "/etc/fstab.bak"

# Maps TrueNAS share names to local mount paths
MOUNT_POINTS = [
    ("Home-Directories", "/mnt/Home-Directories"),
    ("public", "/mnt/public"),
    ("nvr_recordings", "/mnt/nvr-recordings")  # Corrected to use underscore (_)
]

def main():
    print("====================================================")
    print("TrueNAS SCALE Network Drives Auto-Setup Utility")
    print("====================================================")

    # 1. Verify running as root
    if os.geteuid() != 0:
        print("ERROR: This script must be run as root (using sudo).")
        print("Please run: sudo python3 setup_shares.py")
        return

    # 2. Create Mount Folders
    print("\n[1/3] Creating local mount directories...")
    for share, path in MOUNT_POINTS:
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            print(f"✓ Created: {path}")
        else:
            print(f"✓ Already exists: {path}")

    # 3. Modify /etc/fstab safely
    print("\n[2/3] Updating /etc/fstab configuration...")
    
    # Create backup first
    shutil.copyfile(FSTAB_PATH, BACKUP_PATH)
    print(f"✓ Backup of fstab saved to: {BACKUP_PATH}")

    with open(FSTAB_PATH, 'r') as f:
        lines = f.readlines()

    new_lines = []
    
    # Remove any existing truenas-scale entries to start fresh and avoid duplicates or stale incorrect shares
    for line in lines:
        if "//truenas-scale/" in line:
            continue
        new_lines.append(line)

    # Add the three new correct share entries
    for share, path in MOUNT_POINTS:
        fstab_entry = f"//truenas-scale/{share} {path} cifs credentials=/etc/win-credentials,uid=1000,gid=1000,iocharset=utf8,x-systemd.automount 0 0\n"
        new_lines.append(fstab_entry)
        print(f"✓ Added mount entry for: {share} (target: {path})")

    # Write back the updated fstab
    with open(FSTAB_PATH, 'w') as f:
        f.writelines(new_lines)
    print("✓ Successfully updated /etc/fstab.")

    # 4. Reload systemd and mount
    print("\n[3/3] Reloading mounts and applying changes...")
    try:
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        subprocess.run(["mount", "-a"], check=True)
        print("\n====================================================")
        print("🎉 SUCCESS: All TrueNAS shares are now configured and mounted!")
        print("====================================================")
        print("Your folders are mounted at:")
        for share, path in MOUNT_POINTS:
            print(f"  • {path}  -->  //truenas-scale/{share}")
        print("====================================================")
    except subprocess.CalledProcessError as e:
        print(f"\n⚠️ Warning: System reloaded fstab, but mount -a returned an error: {e}")
        print("Please check your network connection and credentials in /etc/win-credentials.")

if __name__ == "__main__":
    main()
