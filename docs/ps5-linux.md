# Linux, and NixOS, on a PS5 at 13.40

Researched 2026-10-26 for a CFI-1116A (launch disc model) on firmware 13.40. Nothing was run
on a console for this research. Each claim says how it was checked:

- **source**: read in the code of the five `ps5-linux` repositories, cloned on 2026-10-26
  (loader `1263263`, patches `1ec6a4a`, image `0605f2b`, tools `f1fa98a`, mwifiex `4bce848`).
- **readme**: stated in those repositories' own READMEs.
- **report**: a release note, issue, article or post, named where it is used.
- **open**: could not be confirmed.

## The answer

1. **Linux on 13.40 is in the official loader's code, not in a release, and not yet proven on
   a retail console.** `ps5-linux/ps5-linux-loader` master routes 13.40 to the 13.xx
   hypervisor path (`source/main.c`, `fw == 0x1340`) with its own offsets table (`off_1340`,
   `source/offsets.c`), added in commit `6b2ba2f` on 2026-10-22 by soniciso1. The commit says
   the tables were derived from the decrypted 13.40 kernel and that "13.40 was also booted on a
   devkit" (source, report). The last tagged release is still v2.5 of 2026-09-05 (3.00 to
   7.61), and the README's per-firmware list names 13.00, 13.20 and 13.60 but not 13.40
   (readme). soniciso1's fork release `v2026.10.22-all11-13` includes 13.40 and says it "needs a
   hardware pass before being treated as proven" (report). Retail reports from 2026-10-26: issue
   #79, a PS5 Digital CFI-2015 on 13.40 running Ubuntu from an external USB SSD, with display
   artifacts under GPU load (loader build not stated); issue #80, a retail PS5 Pro on 13.42 that
   booted the Ubuntu desktop from USB with soniciso1's fork build, where one failed exploit run
   crashed the kernel and only a 60-second power cut cleared it (report, one reporter each). No
   report yet from a launch CFI-1100 console on 13.40.
2. **Never update to 14.xx.** The loader answers "No" for 14.00 and later (readme). Reports put
   the Relapse kernel fix in 14.00 and the hypervisor fix in 14.10 (report, one secondary
   source). 13.60 is the best-supported firmware and the practical ceiling.
3. **NixOS has not been done on a PS5, and it is a smaller job than the PS4 was.** PS5 Linux is
   mainline Linux 7.2.3 plus one patch and one `.config` (source), not a vendor fork; that config
   already enables everything systemd and NixOS need (source); stock mesa supports the GPU
   (source). nixpkgs has `linux_7_2` 7.2.12, mesa 26.2.5 and systemd 262 (checked with nix eval).
4. **The boot lock stays.** Linux needs the exploit on every cold boot (readme: "this is a
   soft-mod"). No persistent or exploit-free boot exists publicly. A warm reboot inside Linux
   uses kexec and needs no exploit (source).
5. **Windows does not run on a PS5**, bare metal or in a VM; nothing was found. Mihawk OS, tested
   on a standard PS5 on 13.40, is a Windows-styled homebrew shell that runs Windows programs
   through Wine, not Windows (report: its README).
6. **The M.2 slot can hold a Linux-only root** with the tools' M.2 flow (source); whether a PCIe
   Gen3 drive works is not documented (open).

## How it boots (source)

1. A USB drive's FAT32 partition holds `bzImage`, `initrd.img`, `cmdline.txt` and optionally
   `vram.txt`. The loader searches `/mnt/usb0/` to `/mnt/usb3/`, then `/mnt/usbN/PS5/Linux/`
   (`source/loader.c`); `path-override.txt` can remap the names. `cmdline.txt` is read into a
   2048-byte buffer, so the command line is at most 2047 characters.
2. Console settings, marked very important in the README: Rest Mode, Supply Power to USB Ports
   set to Always; HDMI Device Link off.
3. Jailbreak with the WebKit Autoloader for 7.61 to 13.60 (readme), then send
   `ps5-linux-loader.elf` to the ELF loader on port 9021.
4. The loader defeats the hypervisor for the detected firmware, stages the kernel, notifies
   "Going to rest mode in 5 seconds" and enters rest mode (`source/main.c`). Wait for the orange
   light to stop blinking, then press power; white means Linux is starting.
5. On resume the hypervisor shellcode copies the kernel and initrd into a code cave and jumps to
   the kernel's 64-bit entry with a `boot_params` block (`shellcode_hv/boot_linux.c`). There is
   no bootloader; the loader is the bootloader.
6. Without `cmdline.txt` the loader uses `root=/dev/sda2 rw rootwait console=ttyTitania0
   console=tty0 video=DP-1:1920x1080@60 mitigations=off idle=halt pci=pcie_bus_perf`
   (`include/config.h`). The images ship `root=LABEL=<distro> ... preempt=full`.
7. Inside Linux the FAT32 partition is mounted at `/boot/efi`; the warm reboot script runs
   `kexec -l /boot/efi/bzImage --initrd=/boot/efi/initrd.img` with `cmdline.txt` and then
   `systemctl kexec -i` (`ps5-linux-tools/ps5-linux-warm-reboot.sh`). Distro switching works the
   same way (`ps5-linux-image/boot/kexec-*.sh`).

Boot USB ports: the front bottom Type-C and the rear Type-A ports; the front top Type-A is USB
2.0 (readme). etaHEN and kstuff are incompatible and cause freezes (readme), so kstuff-lite,
which a normal autoload list starts, has to be left out of a Linux boot.

## The kernel (source)

- `ps5-linux-patches`: `.config` ("Linux/x86 7.2.3 Kernel Configuration"), `linux.patch` and
  `firmware/`. Build: check out kernel.org stable at the version the `.config` names, `git apply
  linux.patch`, copy the `.config`, `make`.
- `linux.patch` changes 89 files: `arch/x86/platform/ps5` (platform, reboot, power-off),
  `drivers/ps5` (southbridge glue, MMIO UART console, SMU and boost, fan, LED, HDMI, CEC,
  buzzer), AHCI for the southbridge, xHCI, the Ethernet PHY (`drivers/net/phy`), Bluetooth,
  amdgpu and display (22 files), HDA audio, the AMD IOMMU and k10temp.
- The GPU is PCI `0x1002:0x13DA`, added by the patch as `CHIP_CYAN_SKILLFISH | AMD_IS_APU`
  next to the BC-250's IDs; graphics IP 10.1.3, gfx1013.
- Firmware: `ps5_vcn.bin` is built in (`CONFIG_EXTRA_FIRMWARE`), a patched linux-firmware
  `navi10_vcn.bin` revision 9 (`firmware/README.md`). Everything else comes from the distro's
  stock `linux-firmware` package (the image definitions install it). Internal Wi-Fi uses the
  `ps5-linux-mwifiex` driver and its NXP IW620 firmware, validated on one CFI-1108A (its
  README).
- The `.config` has, for systemd and NixOS: `DEVTMPFS`, `CGROUPS`, `CGROUP_BPF`,
  `BPF_SYSCALL`, `FHANDLE`, `INOTIFY_USER`, `SIGNALFD`, `TIMERFD`, `EPOLL`, `TMPFS_POSIX_ACL`,
  `TMPFS_XATTR`, `SECCOMP_FILTER`, `NAMESPACES`, `USER_NS`, `DMIID`, `KEXEC`, `KEXEC_FILE`,
  `BLK_DEV_INITRD` with zstd and gzip, `EXT4_FS` and `VFAT_FS` built in; `AUTOFS_FS`,
  `OVERLAY_FS`, `BTRFS_FS`, `DRM_AMDGPU` and `BLK_DEV_NVME` as modules. `IKCONFIG` is off.

## Graphics (source)

Mesa needs no patch. AMD GPUs are identified by the family the kernel reports, not by PCI ID,
and nixpkgs' mesa 26.2.5 handles gfx1013: it identifies the chip, disables its broken compute
queue and enables ray-tracing instructions (`src/amd/common/ac_gpu_info.c`), and addrlib covers
revisions 0x82 to 0x86 (`amdgpu_asic_addr.h`). The Arch image installs stock `mesa` and
`vulkan-radeon` (`distros/arch/image.yaml`). The README recommends `RADV_DEBUG=nohiz` for
graphical glitches, as for the BC-250 (readme). Whether a given console's revision falls in that
range is open until `lspci` and the kernel log are seen on it.

## What works (readme unless noted)

- GPU acceleration, hardware video decode (H.264, HEVC Main and Main 10, VP9 profiles 0 and 2,
  VC-1, MPEG-2) and encode (H.264, HEVC I-frames only).
- 1080p, 1440p and 2160p at 60 Hz broadly; 120 Hz confirmed only at 1440p on one monitor; HDR
  and RGB range are TODO (patches README). Some monitors need `video=DP-1:...` removed.
- Ethernet on all models; Wi-Fi on Marvell (fat and slim) and MediaTek MT7925 (Pro); DualSense
  over internal Bluetooth or a dongle (the patches TODO still lists an xHCI fix "to enable
  Bluetooth": conflict, open).
- Boost: CPU 3.5 GHz and GPU 2.23 GHz with `ps5_control --boost on`; the README says to switch
  the fan on whenever boost is on, as the PS5 OS does. GPU clock and temperature readouts are
  wrong until the SMU driver is done (patches TODO).
- Fan: `ps5_control --fan on`, or a target temperature at
  `/sys/bus/platform/devices/ps5-fan/target_temp` (default 80 C; report, community guide).
- Not supported: standby and resume. The internal SSD is not modified.

## Switching between the PS5 OS and Linux

- PS5 OS to Linux: jailbreak, send the loader, rest mode, power on. Every cold boot.
- Linux to Linux: kexec warm reboot, no exploit.
- Linux to the PS5 OS: a power-off and cold boot; a "Repairing" screen and "wasn't turned off
  properly" message afterwards are normal and harmless (readme).
- A rest-mode "relaunch Linux on power-up" feature is mentioned as possible, not available
  (readme).

## The M.2 slot and a Gen3 SSD

- Linux on M.2 is NVMe only; SATA M.2 does not work (readme). M.2 boot is listed on 4.00 and
  later, including 13.00, 13.20 and 13.60; on 3.xx the PS5 fails to boot with it attached
  (readme).
- The flow (source, `ps5-linux-tools`): `m2_init` writes a fake MBR header and GPT partition
  "that makes PS5 OS happy", `m2_install.sh` formats the M.2 as ext4 and copies a distro image
  onto it, and `m2_exec.sh` kexecs from the USB-booted Linux into the M.2 system. The USB drive
  is still needed for the loader's FAT32 files. The drive then belongs to Linux; the PS5 OS
  cannot store games on it.
- `m2_init` is a Linux program: it opens `/dev/nvme0n1` and writes a protective MBR, a GPT
  header and entries at LBA 65536, inside the layout the PS5 OS wrote when it formatted the
  drive, plus the backup GPT at the end (source). So the PS5 OS must format the drive first,
  and the drive must be one the PS5 OS accepts.
- Sony's page (report, read 2026-10-26): PCIe Gen4 x4 NVMe, 250 GB to 8 TB, 5,500 MB/s
  "recommended", a heatsink required, SATA M.2 not supported, no guarantee for every drive.
  Install and remove the drive only with the console off and unplugged.
- A drive the PS5 OS does not accept can stop it booting with a "not supported, remove it"
  notice (reports 2020 to 2023, one of them a Gen4 drive). What 13.x does with a Gen3 drive is
  not documented (open). The only Gen3 workaround found copies the first 2 MB of a
  PS5-formatted Gen4 drive onto the Gen3 drive, "confirmed working on 4.00, 4.03, 4.51" and
  possibly not on newer firmware (report, one unofficial guide); a PS5-side format wipes it.
- The safe way to use a Gen3 drive is a USB enclosure: Sony's USB guide lists the CFI-1000
  group's front Type-C and both rear Type-A ports at 10 Gbps and the front Type-A at USB 2.0
  (report, read). A community guide says rear ports stopped detecting M.2 enclosures on newer
  kernels and that an enclosure's own sleep can stop it waking (report).
- Image issue #26 closed a data-loss risk in rootfs auto-grow (report).

## The boot lock

The exploit has to run on every cold boot; the loader calls itself a soft-mod (readme). No
persistent bootloader, secure-boot bypass or flash mod for the PS5 was found. The PS5 BootROM
keys were reported dumped on 2025-12-31, without a jailbreak following from it (report,
Notebookcheck 2026-01-02). What is realistic: Y2JB from a cold boot, the loader autoloaded instead
of kstuff-lite, then warm reboots by kexec while Linux runs.

## Stability and safety (report unless noted)

- Byepervisor-Reborn calls its exploit 99.9% stable; the known failure is the console shutting
  down on resume from rest mode.
- Open loader and image issues on 2026-10-26: display artifacts in GPU apps (#79), a mouse freeze
  during Steam downloads (#74), a black screen after a resolution change (#64) and at GDM on 4K
  (#27), and a systemd ordering cycle that can hang boot (#38).
- No bricks or damage to the internal SSD were found.
- One PS5 Slim ran too hot at the 2.23 GHz GPU boost on older firmware.
- Andy Nguyen (TheFloW) stopped PS5 Linux work on 2026-09-15; soniciso1, rmuxnet, gzimbric,
  Ouroboros and EchoStretch carry it on (source: commit authors).
- Gaming: Digital Foundry measured Steam through Proton near native PS5 performance in one
  favourable case at 1080p, on old firmware.

## NixOS: the plan

The PS5 is simpler than the PS4 Linux ports in three places: a mainline kernel, stock mesa, and
an initrd the loader takes as it is.

1. **Kernel**: done as this repository's NixOS module (`module.nix`, options in the README).
   It takes `linux.patch` and `firmware/` from upstream's main branch as a flake input; reading
   that input's `.config` for the target version is not import-from-derivation, because flake
   inputs are fetched before evaluation. The config is nixpkgs' kernel config plus the PS5
   options, the way nixpkgs and nixos-apple-silicon build device kernels, not the project's
   `.config`. The project builds its own kernel with GCC 15.2, no LTO, generic x86-64, and
   `IOMMU_DEFAULT_PASSTHROUGH`; `IKCONFIG` is off there and on in nixpkgs' config. Measured on
   2026-10-26 with `patch --dry-run` (newest patches tag that day: `kernel-7.2.3-1ec6a4a`):
   - nixpkgs' 7.2.12: two hunks fail even with fuzz, `btusb.c` (new upstream flags next to the
     patch's) and one in `amdgpu_dm.c` (display init moved), a small rebase.
   - vanilla 7.3: 16 hunks fail in 8 files, 8 of them in `amdgpu_dm.c`, a real rebase of the
     display hotplug code.
   - CachyOS `cachyos-7.3.0-4` (the source xddxdd/nix-cachyos-kernel built "latest" from that
     day; LTS was 6.18.55): 15 hunks fail in 7 files (`amdgpu_dm.c` 8, `btusb.c` 2, and one each
     in `amdgpu.h`, `amdgpu_drv.c`, `iommu/amd/init.c`, `asm/setup.h`, `kvm/x86.c`). CachyOS's
     own changes add no conflict; the failures are the 7.2 to 7.3 drift. The BORE scheduler
     patch shares no file with `linux.patch`.
   - CachyOS's `config` has `X86_EXTENDED_PLATFORM` off, which `X86_PS5` depends on, and lacks
     `AHCI_SALINA`, `MTS` and the built-in `ps5_vcn.bin`; those go in the patch's
     `structuredExtraConfig`. Its builder sets `ignoreConfigErrors`, so a check must assert
     `CONFIG_X86_PS5=y` in the built kernel's config, or a dropped option goes unnoticed.

   NixOS's `boot.kernelPatches` reaches any `boot.kernelPackages`, the CachyOS builder
   included, so the PS5 patch and its config are one list entry whatever kernel the host
   picks. So: first the exact 7.2.3 pair, then 7.2.12 with the two hunks rebased, and CachyOS
   LTO at `x86-64-v3` (the PS5's Zen 2 has AVX2 and no AVX-512; never `native` or `zen4` when
   ryzen builds it) once a patch applies to its source: upstream's 7.3 tag or our own rebase of
   the 15 hunks.
2. **Firmware**: `ps5_vcn.bin` stays built in; `hardware.firmware` with linux-firmware for the
   rest, and anything a built-in driver requests at probe goes in the initramfs, because a
   built-in driver probes before the root filesystem is mounted.
3. **Boot files**: the FAT32 partition mounted at `/boot/efi`, and `boot.loader.external` with
   an `installHook` that copies the generation's kernel as `bzImage`, its initrd as `initrd.img`
   and a `cmdline.txt` ending in `init=<toplevel>/init` onto it. Then `nixos-rebuild switch`
   updates the next boot, and a kexec warm reboot starts it without the exploit.
4. **Root**: ext4 by label, on the USB drive first, the M.2 later.
5. **Services**: fan and boost as NixOS services built from `ps5-linux-tools`, the IW620 Wi-Fi
   driver as an out-of-tree module, DualSense through internal Bluetooth or a dongle.
6. **The Steam console session**: the project's CachyOS image (source,
   `distros/cachyos/`) autologins a `steam` user on tty1 and runs `gamescope --backend drm -e
   --prefer-output DP-1 --sdr-gamut-wideness 0 -- steam -gamepadui`, with a switch to Plasma and
   back; the console's HDMI output appears as `DP-1`. On NixOS that is
   `programs.steam.gamescopeSession` or Jovian-NixOS (`jovian.steam.enable`, unstable only, no
   gfx1013 report found) with autologin. BC-250 owners, on the same GPU family, use
   `RADV_DEBUG=nohiz` and report panics on kernels 6.15.0 to 6.15.6 and 6.17.8 to 6.17.10
   (report, one community guide).
7. **Deploy**: `nixos-rebuild switch --target-host` from another machine; the console
   builds nothing.

## Before trying it on a 13.40 console

- Wait for a 13.40 report on retail, or accept being the first. The software side can be built
  and booted on the PC in QEMU only up to the kernel's hardware needs; real testing needs the
  console.
- Keep 13.40. If 13.40 stays unproven, updating to 13.60 is the one forward step with the most
  tooling; never 14.xx.
- A 64 GB or larger USB 3 drive in the front Type-C port; a USB keyboard and mouse; Ethernet.
- Run the Y2JB entry without kstuff-lite for a Linux boot. The Y2JB autoloader reads
  `/data/ps5_autoloader_PPSA01650/autoload.txt` before the shared list (itsPLK's README, read on
  2026-10-03), so the Y2JB tile could send only the Linux loader while the WebKit entry keeps
  the normal autoload list. Untested.

## Sources

Read in the cloned repositories: `ps5-linux-loader` (`README.md`, `source/main.c`,
`source/offsets.c`, `source/loader.c`, `include/config.h`, commit `6b2ba2f`),
`ps5-linux-patches` (`README.md`, `.config`, `linux.patch`, `firmware/`), `ps5-linux-image`
(`boot/`, `distros/`), `ps5-linux-tools` (`README.md`, `ps5-linux-warm-reboot.sh`). nixpkgs:
`linux_7_2`, `mesa` source 26.2.5 (`src/amd/common/ac_gpu_info.c`,
`src/amd/addrlib/src/amdgpu_asic_addr.h`), `nixos/modules/system/boot/loader/external`.
Reports: github.com/soniciso1/ps5-linux-loader releases; github.com/PS5Dev/Byepervisor-Reborn
and github.com/EchoStretch/Byepervisor-Reborn (`include/offsets/13_40.h` exists only in the
fork); github.com/mihawk-99/ps5_mihawkos; rmuxnet.gitlab.io/ps5-linux-guide; Notebookcheck
2026-01-02 and 2026-10-16; OMG Ubuntu 2026-10; Gaming On Linux 2026-07 and 2026-09; Phoronix
2026-03-17; github.com/ZigZagBoi1/PS5-14.10-Research (its own claims unverified).
