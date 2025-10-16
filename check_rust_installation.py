"""
Check Rust Installation and Requirements
This script verifies what Rust components are installed on your system.
"""

import shutil
import subprocess
import os

def check_command(cmd_name, version_flag='--version'):
    """Check if a command exists and get its version"""
    path = shutil.which(cmd_name)
    if path:
        try:
            result = subprocess.run(
                [cmd_name, version_flag],
                capture_output=True,
                text=True,
                timeout=5
            )
            version = result.stdout.strip() or result.stderr.strip()
            return True, path, version
        except Exception as e:
            return True, path, f"Found but error getting version: {e}"
    return False, None, None

def main():
    print("=" * 70)
    print("RUST INSTALLATION CHECK")
    print("=" * 70)
    print()
    
    # Check core Rust components
    components = [
        ('rustc', 'Rust Compiler'),
        ('cargo', 'Cargo Package Manager'),
        ('rustup', 'Rust Toolchain Installer'),
        ('rustfmt', 'Rust Code Formatter (optional)'),
        ('clippy-driver', 'Rust Linter (optional)'),
        ('rust-analyzer', 'Language Server (optional)'),
    ]
    
    installed = []
    missing = []
    
    for cmd, description in components:
        found, path, version = check_command(cmd)
        
        if found:
            print(f"✅ {description}")
            print(f"   Command: {cmd}")
            print(f"   Location: {path}")
            if version:
                # Show only first line of version
                first_line = version.split('\n')[0]
                print(f"   Version: {first_line}")
            installed.append(cmd)
        else:
            print(f"❌ {description}")
            print(f"   Command: {cmd}")
            print(f"   Status: NOT FOUND")
            missing.append((cmd, description))
        print()
    
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()
    
    if 'rustc' in installed and 'cargo' in installed:
        print("✅ RUST IS PROPERLY INSTALLED!")
        print()
        print("🎉 Your Rust editor should work perfectly!")
        print()
        print("Core components found:")
        print("  • rustc  - Compiles Rust code")
        print("  • cargo  - Manages projects and dependencies")
        print()
        
        if 'rustup' in installed:
            print("✅ rustup is installed - You can easily update Rust")
            print("   Run: rustup update")
            print()
        
        # Check optional components
        optional_found = [c for c in ['rustfmt', 'clippy-driver', 'rust-analyzer'] if c in installed]
        optional_missing = [c for c in ['rustfmt', 'clippy-driver', 'rust-analyzer'] if c not in installed]
        
        if optional_missing:
            print("📦 OPTIONAL COMPONENTS (Recommended):")
            print()
            if 'rustfmt' not in installed:
                print("  • rustfmt - Auto-format your code")
                print("    Install: rustup component add rustfmt")
                print()
            if 'clippy-driver' not in installed:
                print("  • clippy - Advanced linting and suggestions")
                print("    Install: rustup component add clippy")
                print()
            if 'rust-analyzer' not in installed:
                print("  • rust-analyzer - Better IDE features")
                print("    Install: rustup component add rust-analyzer")
                print()
    else:
        print("❌ RUST IS NOT PROPERLY INSTALLED")
        print()
        print("⚠️  YOUR EDITOR WILL NOT WORK WITHOUT RUST!")
        print()
        print("Missing required components:")
        for cmd, desc in missing:
            if cmd in ['rustc', 'cargo', 'rustup']:
                print(f"  • {desc} ({cmd})")
        print()
        print("=" * 70)
        print("🔧 HOW TO INSTALL RUST:")
        print("=" * 70)
        print()
        print("STEP 1: Download Rust")
        print("  → Visit: https://rustup.rs")
        print("  → Or direct link: https://win.rustup.rs/x86_64")
        print()
        print("STEP 2: Run the installer")
        print("  → Double-click rustup-init.exe")
        print("  → Press Enter to accept defaults")
        print("  → Wait for installation to complete")
        print()
        print("STEP 3: Restart")
        print("  → Close this window")
        print("  → Restart your Rust editor")
        print("  → Run this check script again")
        print()
        print("=" * 70)
        print("⚠️  IMPORTANT: You MUST restart your editor after installing!")
        print("=" * 70)
        print()
        
        # Try to open browser
        try:
            import webbrowser
            print("🌐 Opening Rust installation page in your browser...")
            webbrowser.open('https://rustup.rs')
            print("✅ Browser opened! Follow the instructions there.")
            print()
        except Exception:
            print("❌ Could not open browser automatically.")
            print("   Please manually visit: https://rustup.rs")
            print()
    
    print("=" * 70)
    print("WHAT YOUR EDITOR NEEDS:")
    print("=" * 70)
    print()
    print("REQUIRED (Must have):")
    print("  ✓ rustc  - To compile Rust code")
    print("  ✓ cargo  - To manage Cargo projects")
    print()
    print("OPTIONAL (Nice to have):")
    print("  • rustfmt - Auto-format code")
    print("  • clippy  - Better error messages")
    print("  • rust-analyzer - Enhanced IDE features")
    print()
    print("=" * 70)
    print("YOUR EDITOR FEATURES:")
    print("=" * 70)
    print()
    print("✅ Create Cargo Projects (File → New Cargo Project)")
    print("✅ Run Rust Code (F5 or Rust Run button)")
    print("✅ Fast Error Check (F6 or Cargo Check)")
    print("✅ Syntax Highlighting")
    print("✅ Error Detection")
    print("✅ Auto-add Dependencies (like eframe)")
    print("✅ Compile standalone .rs files")
    print()
    
    # Check PATH
    print("=" * 70)
    print("ENVIRONMENT CHECK:")
    print("=" * 70)
    print()
    cargo_home = os.environ.get('CARGO_HOME', 'Not set')
    rustup_home = os.environ.get('RUSTUP_HOME', 'Not set')
    path = os.environ.get('PATH', '')
    
    print(f"CARGO_HOME: {cargo_home}")
    print(f"RUSTUP_HOME: {rustup_home}")
    print()
    
    # Check if .cargo/bin is in PATH
    cargo_bin_in_path = any('.cargo\\bin' in p or '.cargo/bin' in p for p in path.split(os.pathsep))
    if cargo_bin_in_path:
        print("✅ Cargo bin directory is in PATH")
    else:
        print("⚠️  Cargo bin directory might not be in PATH")
        print("   Expected: C:\\Users\\YourName\\.cargo\\bin")
        print("   You may need to restart your editor after installing Rust")
    print()
    
    print("=" * 70)
    
    # Final status message
    if 'rustc' in installed and 'cargo' in installed:
        print("✅ ALL GOOD! You can start coding in Rust now!")
    else:
        print("❌ PLEASE INSTALL RUST FIRST!")
        print("   Visit: https://rustup.rs")
    
    print("=" * 70)
    print()
    print("Press Enter to close...")
    input()

if __name__ == '__main__':
    main()
