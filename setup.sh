#!/bin/bash
# ==============================================================================
# Project: Shree Voice Assistant - Setup Script
# Author: Senior Python Developer
# Description: This script prepares the system for running the Shree project.
# It performs the following actions:
#   1. Installs essential system-level dependencies for Python and audio.
#   2. Creates a dedicated Python virtual environment ('venv').
#   3. Installs all required Python packages from requirements.txt.
#   4. Creates and populates a .env file with script paths.
#
# Usage:
#   1. Make the script executable: chmod +x setup.sh
#   2. Run the script: ./setup.sh
# ==============================================================================

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
VENV_DIR="venv"
ENV_FILE=".env" # Name of the environment file

# --- Helper Functions ---
log() {
    echo "=============================================================================="
    echo "  $1"
    echo "=============================================================================="
}

# --- Main Setup Logic ---

# Step 1: Install System-Level Dependencies
# These are required by the Python packages in requirements.txt (e.g., PyAudio, gTTS).
install_system_dependencies() {
    log "STEP 1: Installing system dependencies via APT"
    sudo apt-get update
    sudo apt-get install -y \
        python3-dev \
        python3-venv \
        portaudio19-dev \
        mpg123 \
        espeak \
        git \
        libpulse-dev \
        swig \
        bison \
        wget # Added wget for JDK downloads in pkgInstaller.sh
    log "System dependencies installed successfully."
}

# Step 2: Create Python Virtual Environment
setup_virtual_environment() {
    if [ -d "$VENV_DIR" ]; then
        log "STEP 2: Virtual environment '$VENV_DIR' already exists. Skipping creation."
    else
        log "STEP 2: Creating Python virtual environment in './$VENV_DIR'"
        python3 -m venv "$VENV_DIR"
        log "Virtual environment created successfully."
    fi
}

# Step 3: Install Python Packages
install_python_packages() {
    log "STEP 3: Installing Python packages into the virtual environment"
    
    # Activate the virtual environment for this script's context
    source "$VENV_DIR/bin/activate"
    
    # Upgrade pip, setuptools, and wheel to the latest versions
    # This is a best practice that prevents many installation errors.
    echo "--> Upgrading pip, setuptools, and wheel..."
    python -m pip install --upgrade pip setuptools wheel
    
    # Install all packages from requirements.txt
    echo "--> Installing packages from requirements.txt..."
    pip install -r requirements.txt
    
    # Deactivate after installation
    deactivate
    
    log "Python packages installed successfully."
}

# Step 4: Create and Populate .env file
create_env_file() {
    log "STEP 4: Creating and populating .env file"
    
    # Get the directory of the current script
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

    # Define paths to the shell scripts relative to the script's directory
    PKG_INSTALLER_PATH="$SCRIPT_DIR/pkgInstaller.sh"
    GIT_UTILS_PATH="$SCRIPT_DIR/git_utils.sh"
    # Assuming kafka_utils.sh exists if there are Kafka commands
    KAFKA_UTILS_PATH="$SCRIPT_DIR/kafka_utils.sh" 

    echo "# Environment variables for Shree Voice Assistant" > "$ENV_FILE"
    echo "PKG_INSTALLER_SCRIPT=\"$PKG_INSTALLER_PATH\"" >> "$ENV_FILE"
    echo "GIT_UTILS_SCRIPT=\"$GIT_UTILS_PATH\"" >> "$ENV_FILE"
    echo "KAFKA_UTILS_SCRIPT=\"$KAFKA_UTILS_PATH\"" >> "$ENV_FILE" # Add Kafka script path

    log ".env file created and populated successfully."
}


# --- Execution Flow ---
main() {
    install_system_dependencies
    setup_virtual_environment
    install_python_packages
    create_env_file # Call the new function to create .env

    echo
    log "✅ SETUP COMPLETE! ✅"
    echo
    echo "To activate the virtual environment and run the application, use the following commands:"
    echo "1. Activate environment: source $VENV_DIR/bin/activate"
    echo "2. Run the assistant:     python3 Shree.py"
    echo
    echo "To deactivate the environment when you are done, simply type: "
    echo "deactivate"
    echo
    echo "IMPORTANT: After setup, you may need to run 'source .env' in your terminal or restart your terminal"
    echo "           before running Shree.py to ensure the environment variables are loaded."
    echo
}

# Run the main function
main

# filepath: /home/danav/Documents/Shree/ui.py
import customtkinter as ctk
import threading
from PIL import Image
import os

class ShreeUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configure window
        self.title("Shree Voice Assistant")
        self.geometry("800x600")
        
        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Create main frame
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # Add logo/status indicator
        self.status_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.status_frame.grid(row=0, column=0, padx=20, pady=(20,10), sticky="ew")
        
        self.status_label = ctk.CTkLabel(
            self.status_frame, 
            text="Shree is ready...",
            font=("Roboto", 24, "bold")
        )
        self.status_label.grid(row=0, column=0, padx=20, pady=10)
        
        # Add conversation display
        self.conversation_frame = ctk.CTkScrollableFrame(
            self.main_frame,
            height=400
        )
        self.conversation_frame.grid(row=1, column=0, padx=20, pady=(0,20), sticky="nsew")
        
        # Add control buttons
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.grid(row=2, column=0, padx=20, pady=(0,20), sticky="ew")
        
        self.listen_button = ctk.CTkButton(
            self.button_frame,
            text="Start Listening",
            font=("Roboto", 16),
            height=40,
            command=self.toggle_listening
        )
        self.listen_button.grid(row=0, column=0, padx=10)
        
        self.clear_button = ctk.CTkButton(
            self.button_frame,
            text="Clear History",
            font=("Roboto", 16),
            height=40,
            command=self.clear_conversation
        )
        self.clear_button.grid(row=0, column=1, padx=10)
        
        # State variables
        self.is_listening = False
        self.conversation_labels = []

    def toggle_listening(self):
        self.is_listening = not self.is_listening
        if self.is_listening:
            self.listen_button.configure(text="Stop Listening", fg_color="#E64A19")
            self.status_label.configure(text="Listening...")
        else:
            self.listen_button.configure(text="Start Listening", fg_color=["#1F538D", "#1F538D"])
            self.status_label.configure(text="Shree is ready...")

    def add_conversation_entry(self, speaker, text):
        """Add a new conversation entry to the display"""
        frame = ctk.CTkFrame(self.conversation_frame)
        frame.grid(row=len(self.conversation_labels), column=0, padx=10, pady=5, sticky="ew")
        
        label = ctk.CTkLabel(
            frame,
            text=f"{speaker}: {text}",
            font=("Roboto", 14),
            wraplength=600,
            justify="left"
        )
        label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.conversation_labels.append(frame)

    def clear_conversation(self):
        """Clear all conversation entries"""
        for label in self.conversation_labels:
            label.destroy()
        self.conversation_labels = []

def launch_ui():
    app = ShreeUI()
    app.mainloop()
