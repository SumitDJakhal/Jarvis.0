 #!/bin/bash

# git_utils.sh
# Utility script for Git configuration, SSH key management, and GitHub connection checks.
# Designed to be called by the Shree voice assistant.

# IMPORTANT: This script is designed to be run via `sudo bash git_utils.sh ...`.
# We use SUDO_USER to ensure commands operate on the actual user's files and not root's.

set -e # Exit immediately if a command exits with a non-zero status.

# Function to speak text (requires 'espeak' or 'festival' to be installed)
speak_text() {
    if command -v espeak &> /dev/null; then
        espeak "$1" 2>/dev/null
    elif command -v festival &> /dev/null; then
        echo "$1" | festival --tts 2>/dev/null
    else
        echo "Text-to-speech not available. Please install 'espeak' or 'festival' for voice output."
    fi
}

# --- Helper functions ---

check_config() {
    echo "Checking Git user configuration..."
    speak_text "Checking your Git user configuration."
    
    # Run git config as the original user
    local username=$(sudo -u "$SUDO_USER" git config user.name || echo "")
    local useremail=$(sudo -u "$SUDO_USER" git config user.email || echo "")

    if [ -z "$username" ]; then
        echo "Git user.name is not set."
        speak_text "Your Git username is not set."
        return 1 # Indicate failure
    else
        echo "Git user.name: $username"
        speak_text "Your Git username is set to $username."
    fi

    if [ -z "$useremail" ]; then
        echo "Git user.email is not set."
        speak_text "Your Git user email is not set."
        return 1 # Indicate failure
    else
        echo "Git user.email: $useremail"
        speak_text "Your Git user email is set to $useremail."
    fi

    if [ -n "$username" ] && [ -n "$useremail" ]; then
        echo "Git user configuration is complete."
        speak_text "Git user configuration is complete."
        return 0 # Indicate success
    else
        echo "Git user configuration is incomplete."
        speak_text "Git user configuration is incomplete."
        return 1
    fi
}

gen_ssh() {
    local email="$1"
    if [ -z "$email" ]; then
        echo "Error: Email is required to generate SSH key."
        speak_text "Error: Email is required to generate S S H key."
        return 1
    fi

    local ssh_dir="/home/${SUDO_USER:-$(whoami)}/.ssh"
    local ssh_key_path="$ssh_dir/id_rsa" # Default key name

    echo "Generating new SSH key for $email at $ssh_key_path..."
    speak_text "Generating new S S H key for $email."

    # Ensure .ssh directory exists and has correct permissions
    sudo -u "${SUDO_USER:-$(whoami)}" mkdir -p "$ssh_dir"
    sudo -u "${SUDO_USER:-$(whoami)}" chmod 700 "$ssh_dir"

    # Generate the key as the original user, suppress prompts
    # Use -N "" for no passphrase (less secure, but convenient for automation)
    # Use -f to specify filename
    sudo -u "${SUDO_USER:-$(whoami)}" ssh-keygen -t rsa -b 4096 -C "$email" -f "$ssh_key_path" -N ""

    if [ $? -eq 0 ]; then
        echo "SSH key generated successfully."
        speak_text "S S H key generated successfully."
        # Display the public key after generation
        display_ssh
        return 0
    else
        echo "Error: Failed to generate SSH key."
        speak_text "Error: Failed to generate S S H key."
        return 1
    fi
}

display_ssh() {
    local ssh_dir="/home/${SUDO_USER:-$(whoami)}/.ssh"
    local found_keys=0

    echo "--- Checking for public SSH keys in $ssh_dir ---"
    speak_text "Checking for public S S H keys."

    if [ ! -d "$ssh_dir" ]; then
        echo "Error: The .ssh directory does not exist at $ssh_dir."
        speak_text "Error: The S S H directory does not exist."
        return 1
    fi

    for key_file in "$ssh_dir"/*.pub; do
        if [ -f "$key_file" ]; then
            found_keys=1
            echo "--- Public SSH key found: $(basename "$key_file") ---"
            echo "Content for $(basename "$key_file"):"
            sudo -u "${SUDO_USER:-$(whoami)}" cat "$key_file"
            echo "----------------------------------------------------"
            echo "" # Add a newline for better readability between keys
        fi
    done

    if [ "$found_keys" -eq 0 ]; then
        echo "No public SSH keys (*.pub) found at $ssh_dir."
        speak_text "No public S S H key found."
        return 1
    else
        echo "All found SSH keys have been displayed above."
        speak_text "Existing S S H keys have been displayed."
        return 0
    fi
}


guide_github() {
    echo "--- How to Add Your SSH Key to GitHub ---"
    speak_text "Here is how to add your S S H key to G I T H U B."
    echo "1. First, you need to copy your public SSH key."
    echo "   You can do this by running 'display_ssh' command, then manually copy the key."
    echo "   Alternatively, you can use: sudo -u \"${SUDO_USER:-$(whoami)}\" xclip -sel clip < ~/.ssh/id_rsa.pub"
    echo "   (You might need to install 'xclip': sudo apt install xclip)"
    speak_text "Copy your public S S H key to your clipboard."

    echo "2. Go to GitHub in your web browser."
    speak_text "Go to G I T H U B dot com in your web browser."
    echo "   URL: https://github.com/settings/keys"
    
    echo "3. Log in to your GitHub account."
    speak_text "Log in to your G I T H U B account."
    
    echo "4. Click on 'Settings' (usually top right corner)."
    speak_text "Click on Settings."
    
    echo "5. In the sidebar, click on 'SSH and GPG keys'."
    speak_text "In the sidebar, click on S S H and G P G keys."
    
    echo "6. Click the 'New SSH key' or 'Add SSH key' button."
    speak_text "Click the New S S H key button."
    
    echo "7. Give your key a descriptive 'Title' (e.g., 'My Ubuntu Laptop')."
    speak_text "Give your key a descriptive title."
    
    echo "8. Paste your copied public SSH key into the 'Key' field."
    speak_text "Paste your copied public S S H key into the Key field."
    
    echo "9. Click 'Add SSH key'."
    speak_text "Click Add S S H key."
    
    echo "After adding, your key should be listed. You are now ready to test your connection!"
    speak_text "After adding, your key should be listed. You are now ready to test your connection."
    echo "-----------------------------------------"
}

check_conn() {
    echo "Checking SSH connection to GitHub..."
    speak_text "Checking S S H connection to G I T H U B."
    # Run ssh command as the original user
    sudo -u "${SUDO_USER:-$(whoami)}" ssh -T git@github.com -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null 2>&1 | grep -q "You've successfully authenticated"

    if [ $? -eq 0 ]; then
        echo "SSH connection to GitHub successful!"
        speak_text "S S H connection to G I T H U B successful."
        return 0
    else
        echo "SSH connection to GitHub failed. Possible issues:"
        speak_text "S S H connection to G I T H U B failed. Possible issues."
        echo "  - Key not added correctly to GitHub."
        echo "  - Incorrect permissions on your ~/.ssh directory or key files."
        echo "  - Firewall blocking SSH (port 22)."
        echo "  - Incorrect SSH agent setup (though usually not an issue with id_rsa)."
        echo "  Please ensure your public key is added to GitHub and permissions are correct."
        return 1
    fi
}

do_github_connection_flow() {
    echo "--- Starting GitHub SSH Connection Setup Flow ---"
    speak_text "Starting the G I T H U B S S H connection setup flow."

    # Step 1: Check existing Git config
    check_config
    if [ $? -ne 0 ]; then
        echo "Git configuration is incomplete. Please set user.name and user.email first."
        speak_text "G I T configuration is incomplete. Please set username and email first."
        return 1
    fi

    # Step 2: Generate SSH key if not exists
    local ssh_pub_key_path="/home/${SUDO_USER:-$(whoami)}/.ssh/id_rsa.pub"
    if [ ! -f "$ssh_pub_key_path" ]; then
        echo "No SSH key found. Generating a new one."
        speak_text "No S S H key found. Generating a new one."
        echo "Please provide your email address for the SSH key comment:"
        read -r -p "Enter email: " email_for_key
        if [ -z "$email_for_key" ]; then
            echo "Email not provided. SSH key generation aborted."
            speak_text "Email not provided. S S H key generation aborted."
            return 1
        fi
        gen_ssh "$email_for_key"
        if [ $? -ne 0 ]; then
            echo "SSH key generation failed. Aborting connection flow."
            speak_text "S S H key generation failed. Aborting connection flow."
            return 1
        fi
    else
        echo "Existing SSH key found. Displaying it for your reference."
        speak_text "Existing S S H key found. Displaying it for your reference."
        display_ssh
        if [ $? -ne 0 ]; then
            echo "Failed to display existing key. Aborting connection flow."
            speak_text "Failed to display existing key. Aborting connection flow."
            return 1
        fi
    fi

    # Step 3: Guide user to add key to GitHub
    echo "Now, please follow the instructions to add this SSH key to your GitHub account."
    speak_text "Now, please follow the instructions displayed. Press Enter once you have added the key to G I T H U B."
    guide_github
    read -r -p "Press Enter after adding the SSH key to GitHub: "

    # Step 4: Check SSH connection
    echo "Attempting to check SSH connection to GitHub..."
    speak_text "Attempting to check S S H connection to G I T H U B."
    check_conn
    if [ $? -eq 0 ]; then
        speak_text "Congratulations! Your G I T H U B S S H connection is successfully established."
        echo "GitHub SSH connection setup completed successfully!"
    else
        speak_text "Your G I T H U B S S H connection could not be established. Please review the troubleshooting steps displayed."
        echo "GitHub SSH connection setup failed. Please check the troubleshooting steps above."
    fi
}


# --- Main logic to execute functions based on arguments ---\
case "$1" in
    "check_config")
        check_config
        ;;
    "gen_ssh")
        gen_ssh "$2"
        ;;
    "display_ssh")
        display_ssh
        ;;
    "guide_github")
        guide_github
        ;;
    "check_conn")
        check_conn
        ;;
    "do_github_connection_flow")
        do_github_connection_flow
        ;;
    *)
        echo "Usage: git_utils.sh {check_config|gen_ssh <email>|display_ssh|guide_github|check_conn|do_github_connection_flow}"
        speak_text "Usage: G I T utils dot S H, followed by a command."
        exit 1
        ;;
esac
