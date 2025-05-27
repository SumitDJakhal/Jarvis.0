#!/bin/bash

# pkgInstaller.sh
# Unified script for installing, uninstalling, and checking various software packages on Ubuntu.
# Also manages Java Development Kit (JDK) installations and environment variables.
# Designed to be called by the Shree voice assistant.

# IMPORTANT: This script is designed to be run via `sudo bash pkgInstaller.sh ...`.
# We use SUDO_USER to ensure commands operate on the actual user's files and not root's.

set -e # Exit immediately if a command exits with a non-zero status.

# Function to speak text (requires 'espeak' or 'festival' to be installed)
speak_text() {
    # Adding '|| true' to ensure that if espeak/festival fails,
    # the script does NOT exit due to 'set -e'.
    if command -v espeak &> /dev/null; then
        espeak "$1" 2>/dev/null || true
    elif command -v festival &> /dev/null; then
        echo "$1" | festival --tts 2>/dev/null || true
    else
        echo "Text-to-speech not available. Please install 'espeak' or 'festival' for voice output."
    fi
}

# Helper function to get the home directory of the actual user who invoked sudo
get_user_home() {
    echo "$(eval echo "~${SUDO_USER:-$(whoami)}")"
}

ACTION=$1    # Expected action: "install", "uninstall", "check", "set_java_home"
PACKAGE=$2   # Expected package: "git", "jdk", "vscode", etc.
JDK_VERSION=$3 # Optional: for JDK installations/uninstallations (e.g., "11", "17")
CLEAR_METADATA=$4 # Optional: "yes" or "no" for uninstall

echo "Starting package manager script with action: $ACTION, package: $PACKAGE"
speak_text "Starting package manager script."

# --- Helper functions for installation/uninstallation/checking ---\

update_and_upgrade() {
    echo "Updating and upgrading system packages..."
    speak_text "Updating and upgrading system packages."
    sudo apt update || { echo "Error: apt update failed."; speak_text "Apt update failed."; return 1; }
    sudo apt upgrade -y || { echo "Error: apt upgrade failed."; speak_text "Apt upgrade failed."; return 1; }
    echo "System packages updated and upgraded."
    speak_text "System packages updated and upgraded."
    return 0
}

install_package() {
    local package_name=$1
    echo "Installing $package_name..."
    speak_text "Installing $package_name."
    update_and_upgrade || return 1 # Update before installing
    sudo apt install -y "$package_name" || { echo "Error: Failed to install $package_name."; speak_text "Failed to install $package_name."; return 1; }
    echo "$package_name installed successfully."
    speak_text "$package_name installed successfully."
    return 0
}

uninstall_package() {
    local package_name=$1
    echo "Uninstalling $package_name..."
    speak_text "Uninstalling $package_name."
    sudo apt remove -y "$package_name" || { echo "Error: Failed to remove $package_name."; speak_text "Failed to remove $package_name."; return 1; }
    sudo apt autoremove -y || { echo "Error: Failed to autoremove packages."; speak_text "Failed to autoremove packages."; return 1; }
    echo "$package_name uninstalled successfully."
    speak_text "$package_name uninstalled successfully."
    return 0
}

# New: Function to check if a package is installed
check_package_exists() {
    local package_name=$1
    echo "Checking if $package_name is installed..."
    if dpkg -s "$package_name" &> /dev/null; then
        echo "$package_name is installed."
        speak_text "$package_name is installed."
        return 0 # Installed
    else
        echo "$package_name is NOT installed."
        speak_text "$package_name is not installed."
        return 1 # Not installed
    fi
}

# --- Specific Installation Functions ---

install_git() {
    echo "Installing Git..."
    speak_text "Installing Git."
    install_package git || return 1
    sudo -u "$SUDO_USER" git --version || true # Check version as user, allow failure if not in PATH immediately
    echo "Git installation complete."
    speak_text "Git installation complete."
    return 0
}

install_jdk() {
    local version=$1
    if [ -z "$version" ]; then
        echo "Error: JDK version not specified for installation."
        speak_text "Error: J D K version not specified for installation."
        return 1
    fi

    echo "Attempting to install OpenJDK $version..."
    speak_text "Attempting to install Open J D K version $version."

    local user_home=$(get_user_home)
    local java_install_dir="$user_home/java" # User's personal Java installation directory
    local jdk_tarball=""
    local jdk_folder_name=""
    local download_url=""

    case "$version" in
        "11")
            download_url="https://github.com/adoptium/temurin11-binaries/releases/download/jdk-11.0.23%2B9/OpenJDK11U-jdk_x64_linux_hotspot_11.0.23_9.tar.gz"
            jdk_folder_name="jdk-11"
            ;;
        "17")
            download_url="https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.11%2B9/OpenJDK17U-jdk_x64_linux_hotspot_17.0.11_9.tar.gz"
            jdk_folder_name="jdk-17"
            ;;
        "21")
            download_url="https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.3%2B9/OpenJDK21U-jdk_x64_linux_hotspot_21.0.3_9.tar.gz"
            jdk_folder_name="jdk-21"
            ;;
        *)
            echo "Error: Unsupported JDK version '$version'. Supported versions are 11, 17, 21."
            speak_text "Error: Unsupported J D K version $version. Supported versions are eleven, seventeen, twenty one."
            return 1
            ;;
    esac

    local temp_tarball="/tmp/openjdk-${version}.tar.gz"
    local extracted_path="/tmp/extracted_jdk"

    # Create user's java install directory
    sudo -u "$SUDO_USER" mkdir -p "$java_install_dir" || { echo "Error: Could not create $java_install_dir."; speak_text "Could not create J D K installation directory."; return 1; }

    # Download JDK tarball
    echo "Downloading JDK $version from $download_url..."
    speak_text "Downloading J D K version $version."
    wget -q --show-progress -O "$temp_tarball" "$download_url" || { echo "Error: Failed to download JDK $version."; speak_text "Failed to download J D K version $version."; return 1; }

    # Extract JDK
    echo "Extracting JDK $version to temporary location..."
    speak_text "Extracting J D K version $version."
    sudo mkdir -p "$extracted_path" || { echo "Error: Could not create temp extraction path."; speak_text "Could not create temporary extraction path."; return 1; }
    sudo tar -xzf "$temp_tarball" -C "$extracted_path" --strip-components=1 || { echo "Error: Failed to extract JDK $version."; speak_text "Failed to extract J D K version $version."; return 1; }
    
    # Move extracted JDK to user's java install directory
    echo "Moving JDK to $java_install_dir/$jdk_folder_name..."
    sudo mv "$extracted_path" "$java_install_dir/$jdk_folder_name" || { echo "Error: Failed to move extracted JDK."; speak_text "Failed to move extracted J D K."; return 1; }

    # Clean up temporary tarball and extraction directory
    sudo rm -f "$temp_tarball" || true
    sudo rm -rf "/tmp/extracted_jdk" || true

    # Set JAVA_HOME for this JDK installation
    set_java_home "$java_install_dir/$jdk_folder_name" "$version" || return 1

    echo "OpenJDK $version installed and JAVA_HOME configured successfully."
    speak_text "Open J D K version $version installed and J A V A home configured successfully."
    return 0
}

# New: Function to set JAVA_HOME and add to PATH in user's profile
set_java_home() {
    local jdk_path="$1"
    local version="$2"
    local profile_file="$(get_user_home)/.bashrc" # Default to .bashrc, could be .profile or .zshrc
    
    echo "Setting JAVA_HOME to $jdk_path for user $SUDO_USER..."
    speak_text "Setting J A V A home to $jdk_path."

    local export_line_java="export JAVA_HOME=\"$jdk_path\""
    local export_line_path="export PATH=\"\$PATH:\$JAVA_HOME/bin\""
    
    # Use a unique identifier to prevent duplicate entries
    local marker_start="# --- Added by Shree for JDK $version ---"
    local marker_end="# --- End Shree JDK $version ---"

    # Remove existing entries for this JDK version before adding new ones
    if sudo -u "$SUDO_USER" grep -q "$marker_start" "$profile_file" &> /dev/null; then
        echo "Removing existing JDK $version configuration from $profile_file..."
        sudo -u "$SUDO_USER" sed -i "/$marker_start/,/$marker_end/d" "$profile_file" || { echo "Error: Failed to clean old JDK path in $profile_file."; speak_text "Failed to clean old J D K path."; return 1; }
    fi

    echo "Adding JDK $version configuration to $profile_file..."
    {
        echo "" # Add a newline for separation
        echo "$marker_start"
        echo "$export_line_java"
        echo "$export_line_path"
        echo "$marker_end"
    } | sudo -u "$SUDO_USER" tee -a "$profile_file" > /dev/null || { echo "Error: Failed to add JDK path to $profile_file."; speak_text "Failed to add J D K path."; return 1; }

    echo "JDK $version environment variables updated in $profile_file."
    speak_text "J D K version $version environment variables updated."
    echo "Please source your ~/.bashrc (or open a new terminal) for changes to take effect: source $profile_file"
    speak_text "Please source your bash R C or open a new terminal for changes to take effect."
    return 0
}

# --- Specific Uninstallation Functions ---

uninstall_git() {
    echo "Uninstalling Git..."
    speak_text "Uninstalling Git."
    uninstall_package git || return 1
    echo "Git uninstallation complete."
    speak_text "Git uninstallation complete."
    return 0
}

uninstall_jdk() {
    local version=$1
    local clear_metadata=$2 # "yes" to remove files, "no" to only clear path
    if [ -z "$version" ]; then
        echo "Error: JDK version not specified for uninstallation."
        speak_text "Error: J D K version not specified for uninstallation."
        return 1
    fi

    local user_home=$(get_user_home)
    local java_install_dir="$user_home/java"
    local jdk_folder_name=""
    local profile_file="$(get_user_home)/.bashrc"

    case "$version" in
        "11") jdk_folder_name="jdk-11" ;;
        "17") jdk_folder_name="jdk-17" ;;
        "21") jdk_folder_name="jdk-21" ;;
        *)
            echo "Error: Unsupported JDK version '$version' for uninstallation."
            speak_text "Error: Unsupported J D K version $version for uninstallation."
            return 1
            ;;
    esac

    local full_jdk_path="$java_install_dir/$jdk_folder_name"

    # Remove JAVA_HOME and PATH entries from profile
    echo "Removing JAVA_HOME configuration for JDK $version from $profile_file..."
    local marker_start="# --- Added by Shree for JDK $version ---"
    local marker_end="# --- End Shree JDK $version ---"
    if sudo -u "$SUDO_USER" grep -q "$marker_start" "$profile_file" &> /dev/null; then
        sudo -u "$SUDO_USER" sed -i "/$marker_start/,/$marker_end/d" "$profile_file" || { echo "Warning: Failed to clean old JDK path in $profile_file. Manual cleanup may be required."; speak_text "Failed to clean old J D K path."; }
    else
        echo "No existing JAVA_HOME configuration found for JDK $version in $profile_file."
    fi

    # Remove JDK files if clear_metadata is "yes"
    if [[ "$clear_metadata" == "yes" ]]; then
        echo "Removing JDK $version installation files from $full_jdk_path..."
        speak_text "Removing J D K version $version installation files."
        if sudo -u "$SUDO_USER" [ -d "$full_jdk_path" ]; then
            sudo -u "$SUDO_USER" rm -rf "$full_jdk_path" || { echo "Error: Failed to remove JDK $version files."; speak_text "Failed to remove J D K files."; return 1; }
            echo "JDK $version files removed."
            speak_text "J D K version $version files removed."
        else
            echo "JDK $version installation directory not found at $full_jdk_path. Skipping file removal."
            speak_text "J D K version $version installation directory not found. Skipping file removal."
        fi
    else
        echo "Skipping removal of JDK $version installation files. Only environment variables were cleared."
        speak_text "Skipping removal of J D K files. Only environment variables were cleared."
    fi

    echo "JDK $version uninstallation complete."
    speak_text "J D K version $version uninstallation complete."
    return 0
}


# --- Main logic to execute functions based on arguments ---
case "$ACTION" in
    "install")
        case "$PACKAGE" in
            "git")
                install_git
                ;;
            "jdk")
                install_jdk "$JDK_VERSION"
                ;;
            # Add more installation cases here (vscode, android_studio, neovim, neofetch, snap, wireshark, kafka)
            "vscode")
                echo "Installing VS Code..."
                speak_text "Installing V S Code."
                # Add VS Code installation steps here (e.g., download .deb, dpkg -i)
                # For simplicity, using generic apt install if available:
                install_package code || return 1 # Assuming 'code' package name for VS Code
                ;;
            "android_studio")
                echo "Installing Android Studio..."
                speak_text "Installing Android Studio."
                # Android Studio often requires manual download and extraction
                # For basic apt install, check if it's in a repo:
                install_package android-studio || return 1
                ;;
            "neovim")
                echo "Installing Neovim..."
                speak_text "Installing Neovim."
                install_package neovim || return 1
                ;;
            "neofetch")
                echo "Installing Neofetch..."
                speak_text "Installing Neofetch."
                install_package neofetch || return 1
                ;;
            "snap")
                echo "Installing Snapd..."
                speak_text "Installing Snapd."
                install_package snapd || return 1
                ;;
            "wireshark")
                echo "Installing Wireshark..."
                speak_text "Installing Wireshark."
                install_package wireshark || return 1
                sudo usermod -aG wireshark "$SUDO_USER" || true # Add user to wireshark group
                echo "Please log out and log back in for Wireshark group changes to take effect."
                speak_text "Please log out and log back in for Wireshark group changes to take effect."
                ;;
            "kafka")
                echo "Installing Kafka (requires Java)..."
                speak_text "Installing Kafka. This requires Java."
                # Kafka is usually downloaded and extracted, not via apt
                # This would be a more complex installation, potentially requiring Zookeeper setup.
                # For a basic placeholder:
                echo "Kafka installation is complex and typically involves manual steps. Please refer to official documentation."
                speak_text "Kafka installation is complex and typically involves manual steps."
                return 1
                ;;
            *)\
                echo "Error: Unknown package for installation: $PACKAGE."
                speak_text "Error: Unknown package for installation."
                exit 1
                ;;
        esac
        ;;
    "uninstall")
        case "$PACKAGE" in
            "git")
                uninstall_git
                ;;
            "jdk")
                uninstall_jdk "$JDK_VERSION" "$CLEAR_METADATA"
                ;;
            # Add more uninstallation cases here
            "vscode")
                echo "Uninstalling VS Code..."
                speak_text "Uninstalling V S Code."
                uninstall_package code || return 1
                ;;
            "android_studio")
                echo "Uninstalling Android Studio..."
                speak_text "Uninstalling Android Studio."
                uninstall_package android-studio || return 1
                ;;
            "neovim")
                echo "Uninstalling Neovim..."
                speak_text "Uninstalling Neovim."
                uninstall_package neovim || return 1
                ;;
            "neofetch")
                echo "Uninstalling Neofetch..."
                speak_text "Uninstalling Neofetch."
                uninstall_package neofetch || return 1
                ;;
            "snap")
                echo "Uninstalling Snapd..."
                speak_text "Uninstalling Snapd."
                uninstall_package snapd || return 1
                ;;
            "wireshark")
                echo "Uninstalling Wireshark..."
                speak_text "Uninstalling Wireshark."
                uninstall_package wireshark || return 1
                sudo deluser "$SUDO_USER" wireshark || true # Remove user from wireshark group
                ;;
            "kafka")
                echo "Uninstalling Kafka..."
                speak_text "Uninstalling Kafka."
                echo "Kafka uninstallation is complex and typically involves manual steps."
                speak_text "Kafka uninstallation is complex and typically involves manual steps."
                return 1
                ;;
            *)\
                echo "Error: Unknown package for uninstallation: $PACKAGE."
                speak_text "Error: Unknown package for uninstallation."
                exit 1
                ;;
        esac
        ;;
    "check")
        case "$PACKAGE" in
            "git")
                check_package_exists git
                ;;
            "jdk")
                # For JDK, check for /home/user/java/jdk-<version> directory and JAVA_HOME setting
                local version=$JDK_VERSION
                local user_home=$(get_user_home)
                local expected_path="$user_home/java/jdk-$version"
                
                echo "Checking if JDK $version is installed at $expected_path..."
                speak_text "Checking if J D K version $version is installed."

                if sudo -u "$SUDO_USER" [ -d "$expected_path" ]; then
                    echo "JDK $version files found at $expected_path."
                    # Also check if JAVA_HOME is set to this path in current session (less reliable for external check)
                    # For a full check, we might need to parse .bashrc, which is more complex.
                    # For now, file presence is a good indicator.
                    speak_text "J D K version $version files found."
                    return 0
                else
                    echo "JDK $version files NOT found at $expected_path."
                    speak_text "J D K version $version files not found."
                    return 1
                fi
                ;;
            # Add more check cases here
            "vscode")
                check_package_exists code # Assuming 'code' package name for VS Code
                ;;
            "android_studio")
                check_package_exists android-studio
                ;;
            "neovim")
                check_package_exists neovim
                ;;
            "neofetch")
                check_package_exists neofetch
                ;;
            "snap")
                check_package_exists snapd
                ;;
            "wireshark")
                check_package_exists wireshark
                ;;
            "kafka")
                echo "Checking for Kafka installation is complex. Please check manually."
                speak_text "Checking for Kafka installation is complex. Please check manually."
                return 1
                ;;
            *)\
                echo "Error: Unknown package for check: $PACKAGE."
                speak_text "Error: Unknown package for check."
                exit 1
                ;;
        esac
        ;;
    "set_java_home")
        set_java_home "$PACKAGE" "$JDK_VERSION" # PACKAGE here is the full path, JDK_VERSION is the version
        ;;
    *)\
        echo "Error: Invalid action: $ACTION. Must be 'install', 'uninstall', 'check', or 'set_java_home'."
        speak_text "Error: Invalid action. Must be install, uninstall, check, or set J A V A home."
        exit 1
        ;;
esac

echo "Package manager script finished."
speak_text "Package manager script finished."
exit 0
