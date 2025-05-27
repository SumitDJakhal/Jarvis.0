#!/usr/bin/env python3
# Ubuntu Linux Voice Assistant - Shree

import speech_recognition as sr  # Speech recognition
import subprocess
import os
import logging
from gtts import gTTS  # Google Text-to-Speech
from dotenv import load_dotenv  # For secure env variables
import time # Import time for delays

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("shree.log"), # Changed log file name
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("shree") # Changed logger name

# Load environment variables from .env file
load_dotenv()

def speak(text):
    """Convert text to speech using gTTS"""
    try:
        logger.info(f"Speaking: {text}")
        print(f"Shree: {text}") # Changed assistant name in print
        tts = gTTS(text=text, lang='en')
        tts.save("output.mp3")
        # Use a more robust way to play audio that handles potential issues
        # with mpg123 not being found or permissions.
        try:
            subprocess.run(['mpg123', "-q", "output.mp3"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            logger.error("mpg123 not found. Please install it (e.g., sudo apt install mpg123).")
            print("Error: mpg123 not found. Cannot play audio.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error playing audio with mpg123: {e}")
            print(f"Error playing audio: {e}")
        finally:
            if os.path.exists("output.mp3"):
                os.remove("output.mp3")  # Clean up the temporary file
    except Exception as e:
        logger.error(f"Error in speak function: {e}")

def takeCommand():
    """Take microphone input from the user and return string output"""
    r = sr.Recognizer()
    
    try:
        with sr.Microphone() as source:
            print("Listening...")
            r.adjust_for_ambient_noise(source, duration=0.5)
            r.pause_threshold = 1
            audio = r.listen(source, timeout=5, phrase_time_limit=5)
        
        print("Recognizing...")
        query = r.recognize_google(audio, language='en-in')
        print(f"User said: {query}")
        return query.lower()
    
    except sr.WaitTimeoutError:
        logger.info("Timeout occurred while listening")
        return "None"
    except sr.UnknownValueError:
        logger.info("Could not understand audio")
        print("I didn't catch that. Could you repeat?")
        return "None"
    except sr.RequestError as e:
        logger.error(f"Google Speech Recognition service error: {e}")
        print(f"Speech service error: {e}")
        return "None"
    except Exception as e:
        logger.error(f"Error in takeCommand: {e}")
        print(f"Error: {e}")
        return "None"

def get_confirmation_for_metadata_clear():
    """Asks the user for confirmation to clear metadata and returns 'yes' or 'no'."""
    speak("Would you like to clear all associated configuration files and metadata? Say yes or no.")
    print("Clear associated configuration files and metadata? (yes/no)")
    
    for i in range(3): # Max 3 attempts for confirmation
        confirmation_query = takeCommand()
        if "yes" in confirmation_query:
            return "yes"
        elif "no" in confirmation_query:
            return "no"
        else:
            speak("I didn't understand. Please say 'yes' or 'no'.")
            if i == 2: # Last attempt, offer typing
                speak("I'm still having trouble understanding your confirmation. Please type 'yes' or 'no'.")
                typed_confirmation = input("Type 'yes' to clear metadata, or 'no' to keep it: ").strip().lower()
                if typed_confirmation in ["yes", "no"]:
                    return typed_confirmation
                else:
                    speak("Invalid input. Assuming 'no' for metadata clearing.")
                    return "no"
    return "no" # Default to 'no' if all attempts fail

def execute_shell_script(script_name, *args):
    """Helper function to execute any shell script."""
    # Get script path from environment variables
    if script_name == 'pkgInstaller.sh':
        script_path = os.getenv('PKG_INSTALLER_SCRIPT')
    elif script_name == 'git_utils.sh':
        script_path = os.getenv('GIT_UTILS_SCRIPT')
    elif script_name == 'kafka_utils.sh':
        script_path = os.getenv('KAFKA_UTILS_SCRIPT')
    else:
        logger.error(f"Unknown script name: {script_name}")
        speak(f"I don't know how to run the script called {script_name}.")
        return False

    if not script_path or not os.path.exists(script_path):
        logger.error(f"{script_name} not found at {script_path}. Check .env file and script location.")
        speak(f"The script, {script_name}, was not found. Please ensure it is in the correct location and the .env file is configured.")
        return False

    try:
        # Ensure the script is executable
        chmod_command = ['chmod', '+x', script_path]
        logger.info(f"Executing: {' '.join(chmod_command)}")
        subprocess.run(chmod_command, check=True)
        
        # Run the script with sudo and all provided arguments
        command = ['sudo', 'bash', script_path] + list(args)
        logger.info(f"Executing: {' '.join(command)}")
        subprocess.run(command, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing {script_name}: Command '{' '.join(e.cmd)}' returned non-zero exit status {e.returncode}.")
        speak(f"There was an error running {script_name}. The command '{' '.join(e.cmd)}' failed. Please check the logs for details.")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during {script_name} execution: {e}")
        speak(f"An unexpected error occurred while running {script_name}. Please check the logs.")
        return False

def install_git():
    """Install Git using the unified package manager script."""
    speak("Installing Git now.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'git'):
        speak("Git has been installed successfully.")

def uninstall_git():
    """Uninstall Git using the unified package manager script."""
    speak("Uninstalling Git now.")
    clear_metadata = get_confirmation_for_metadata_clear()
    if execute_shell_script('pkgInstaller.sh', 'uninstall', 'git', clear_metadata):
        speak("Git has been uninstalled successfully.")

def check_git_configuration():
    """Checks Git user.name and user.email configuration."""
    speak("Checking your Git user configuration.")
    execute_shell_script('git_utils.sh', 'check_config')

def generate_and_display_ssh_key():
    """Generates and displays an SSH key."""
    speak("To generate an SSH key, I need your email address for the key comment.")
    print("Please type your email for the SSH key comment (e.g., 'your_email@example.com'):")
    user_email = input().strip()
    if not user_email:
        speak("No email provided. SSH key generation aborted.")
        print("No email provided. SSH key generation aborted.")
        return
    
    speak("Generating and displaying your SSH key now.")
    execute_shell_script('git_utils.sh', 'gen_ssh', user_email)
    execute_shell_script('git_utils.sh', 'display_ssh')

def guide_github_connection():
    """Guides the user on how to add SSH key to GitHub."""
    speak("I will now guide you on how to add your SSH key to GitHub.")
    execute_shell_script('git_utils.sh', 'guide_github')

def check_github_ssh_connection():
    """Checks if the SSH connection to GitHub is successful."""
    speak("Checking your SSH connection to GitHub.")
    execute_shell_script('git_utils.sh', 'check_conn')

def do_github_connection_flow():
    """Starts the full GitHub SSH connection setup flow."""
    speak("Starting the GitHub connection setup flow.")
    execute_shell_script('git_utils.sh', 'do_github_connection_flow')


def install_jdk():
    """Install a specific OpenJDK version using the unified package manager script."""
    valid_versions = ["11", "17", "21"] # Common LTS versions
    jdk_version = None
    
    # --- Step 1: Get JDK Version (Voice or Type) ---
    speak("Which OpenJDK version would you like to install? For example, you can say 11, 17, or 21.")
    print("Which OpenJDK version would you like to install? (e.g., 11, 17, 21)")

    version_obtained = False
    for i in range(3): # Max 3 attempts for voice recognition of version
        if not version_obtained:
            speak(f"Attempt {i+1} for voice input.")
            query = takeCommand()
            if query != "None":
                found_versions = [v for v in valid_versions if v in query]
                if found_versions:
                    jdk_version = found_versions[0]
                    version_obtained = True
                    break
                else:
                    speak("I heard something, but it doesn't sound like a valid JDK version.")
            else:
                speak("I didn't catch that.")
        
        if not version_obtained and i < 2: # Offer typing after 1st and 2nd voice attempt failures
            speak("Would you like to type the version instead?")
            print("Type 'yes' to type, or 'no' to try voice again:")
            type_choice = takeCommand() # Try to get voice input for choice
            if "yes" in type_choice:
                print("Please type the JDK version (e.g., 11, 17, 21): ")
                typed_version = input().strip()
                if typed_version in valid_versions:
                    jdk_version = typed_version
                    version_obtained = True
                    break
                else:
                    speak("Invalid version typed. Let's try voice again.")
                    print("Invalid version typed. Trying voice again.")
            elif "no" in type_choice:
                speak("Okay, trying voice again.")
            else:
                speak("I didn't understand your choice. Let's try voice again.")

    if not version_obtained: # If still no version after all attempts
        speak("I'm having trouble getting the JDK version. Please type it now.")
        print("Please type the JDK version (e.g., 11, 17, 21): ")
        typed_version = input().strip()
        if typed_version in valid_versions:
            jdk_version = typed_version
            version_obtained = True
        else:
            speak("Invalid version entered. Aborting JDK installation.")
            print("Invalid version entered. Aborting JDK installation.")
            return

    if jdk_version not in valid_versions:
        speak(f"The version {jdk_version} is not a common LTS version I can install. Please choose from {', '.join(valid_versions)}.")
        return

    # --- Step 2: Confirm JDK Version (Voice or Type) ---
    confirmed = False
    for i in range(3): # Max 3 attempts for confirmation
        speak(f"You said version {jdk_version}. Is that correct? Say yes or no.")
        print(f"Confirm JDK version {jdk_version}. Say 'yes' or 'no'.")
        confirmation_query = takeCommand()

        if "yes" in confirmation_query:
            confirmed = True
            break
        elif "no" in confirmation_query:
            speak("Okay, let's restart the version selection process.")
            speak("Installation aborted as you indicated the version was incorrect.")
            return
        else:
            speak("I didn't understand your confirmation. Please say 'yes' or 'no' again.")
            if i == 2: # Last attempt, offer typing
                speak("I'm still having trouble understanding your confirmation. Please type 'yes' or 'no'.")
                print("Type 'yes' to confirm, or 'no' to abort:")
                typed_confirmation = input().strip().lower()
                if typed_confirmation == "yes":
                    confirmed = True
                elif typed_confirmation == "no":
                    speak("Installation aborted as you indicated the version was incorrect.")
                    return
                else:
                    speak("Invalid input. Aborting JDK installation.")
                    return

    if not confirmed:
        speak("Could not confirm JDK version. Aborting installation.")
        return

    # --- Proceed with installation if confirmed ---
    speak(f"Okay, I will now attempt to install OpenJDK version {jdk_version}. This may require your sudo password.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'jdk', jdk_version): # Pass version to manager
        speak(f"OpenJDK version {jdk_version} installed successfully.")
        speak("Environment variables for Java are typically set by the system after installation, or you might need to restart your terminal.")
        print("Note: For persistent JAVA_HOME and PATH, you may need to add them to your shell's profile (e.g., ~/.bashrc) and source it.")

def uninstall_jdk():
    """Uninstall a specific OpenJDK version using the unified package manager script."""
    valid_versions = ["11", "17", "21"] # Common LTS versions
    jdk_version = None
    
    speak("Which OpenJDK version would you like to uninstall? For example, you can say 11, 17, or 21.")
    print("Which OpenJDK version would you like to uninstall? (e.g., 11, 17, 21)")

    version_obtained = False
    for i in range(3):
        if not version_obtained:
            speak(f"Attempt {i+1} for voice input.")
            query = takeCommand()
            if query != "None":
                found_versions = [v for v in valid_versions if v in query]
                if found_versions:
                    jdk_version = found_versions[0]
                    version_obtained = True
                    break
                else:
                    speak("I heard something, but it doesn't sound like a valid JDK version.")
            else:
                speak("I didn't catch that.")
        
        if not version_obtained and i < 2:
            speak("Would you like to type the version instead?")
            print("Type 'yes' to type, or 'no' to try voice again:")
            type_choice = takeCommand()
            if "yes" in type_choice:
                print("Please type the JDK version (e.g., 11, 17, 21): ")
                typed_version = input().strip()
                if typed_version in valid_versions:
                    jdk_version = typed_version
                    version_obtained = True
                    break
                else:
                    speak("Invalid version typed. Let's try voice again.")
            elif "no" in type_choice:
                speak("Okay, trying voice again.")
            else:
                speak("I didn't understand your choice. Let's try voice again.")

    if not version_obtained:
        speak("I'm having trouble getting the JDK version. Please type it now.")
        print("Please type the JDK version (e.g., 11, 17, 21): ")
        typed_version = input().strip()
        if typed_version in valid_versions:
            jdk_version = typed_version
            version_obtained = True
        else:
            speak("Invalid version entered. Aborting JDK uninstallation.")
            print("Invalid version entered. Aborting JDK uninstallation.")
            return

    if jdk_version not in valid_versions:
        speak(f"The version {jdk_version} is not a common LTS version I can uninstall. Please choose from {', '.join(valid_versions)}.")
        return

    speak(f"Okay, I will now attempt to uninstall OpenJDK version {jdk_version}. This may require your sudo password.")
    clear_metadata = get_confirmation_for_metadata_clear()
    if execute_shell_script('pkgInstaller.sh', 'uninstall', 'jdk', jdk_version, clear_metadata):
        speak(f"OpenJDK version {jdk_version} has been uninstalled successfully.")


def install_vscode():
    """Install Visual Studio Code using the unified package manager script."""
    speak("Installing Visual Studio Code now.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'vscode'):
        speak("Visual Studio Code has been installed successfully.")

def uninstall_vscode():
    """Uninstall Visual Studio Code using the unified package manager script."""
    speak("Uninstalling Visual Studio Code now.")
    clear_metadata = get_confirmation_for_metadata_clear()
    if execute_shell_script('pkgInstaller.sh', 'uninstall', 'vscode', clear_metadata):
        speak("Visual Studio Code has been uninstalled successfully.")

def install_android_studio():
    """Install Android Studio using the unified package manager script."""
    speak("Installing Android Studio now.")
    speak("This will download a large file and may take a while.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'android_studio'):
        speak("Android Studio installation process completed. Remember to log out and log back in for KVM group changes to take effect.")

def uninstall_android_studio():
    """Uninstall Android Studio using the unified package manager script."""
    speak("Uninstalling Android Studio now.")
    clear_metadata = get_confirmation_for_metadata_clear()
    if execute_shell_script('pkgInstaller.sh', 'uninstall', 'android_studio', clear_metadata):
        speak("Android Studio has been uninstalled successfully.")

def install_neovim():
    """Install Neovim using the unified package manager script."""
    speak("Installing Neovim now.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'neovim'):
        speak("Neovim has been installed successfully.")

def uninstall_neovim():
    """Uninstall Neovim using the unified package manager script."""
    speak("Uninstalling Neovim now.")
    clear_metadata = get_confirmation_for_metadata_clear()
    if execute_shell_script('pkgInstaller.sh', 'uninstall', 'neovim', clear_metadata):
        speak("Neovim has been uninstalled successfully.")

def install_neofetch():
    """Install Neofetch using the unified package manager script."""
    speak("Installing Neofetch now.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'neofetch'):
        speak("Neofetch has been installed successfully.")

def uninstall_neofetch():
    """Uninstall Neofetch using the unified package manager script."""
    speak("Uninstalling Neofetch now.")
    clear_metadata = get_confirmation_for_metadata_clear()
    if execute_shell_script('pkgInstaller.sh', 'uninstall', 'neofetch', clear_metadata):
        speak("Neofetch has been uninstalled successfully.")

def install_snap():
    """Install Snapd using the unified package manager script."""
    speak("Installing Snapd now.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'snap'):
        speak("Snapd has been installed successfully.")

def uninstall_snap():
    """Uninstall Snapd using the unified package manager script."""
    speak("Uninstalling Snapd now.")
    clear_metadata = get_confirmation_for_metadata_clear()
    if execute_shell_script('pkgInstaller.sh', 'uninstall', 'snap', clear_metadata):
        speak("Snapd has been uninstalled successfully.")

def install_wireshark():
    """Install Wireshark using the unified package manager script."""
    speak("Installing Wireshark now.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'wireshark'):
        speak("Wireshark has been installed successfully.")
        speak("Remember to log out and log back in for group changes to take effect and to capture packets without sudo.")

def uninstall_wireshark():
    """Uninstall Wireshark using the unified package manager script."""
    speak("Uninstalling Wireshark now.")
    clear_metadata = get_confirmation_for_metadata_clear()
    if execute_shell_script('pkgInstaller.sh', 'uninstall', 'wireshark', clear_metadata):
        speak("Wireshark has been uninstalled successfully.")

def install_kafka():
    """Install Apache Kafka using the unified package manager script."""
    speak("Installing Apache Kafka now.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'kafka'):
        speak("Apache Kafka installation process initiated. Please follow the instructions in the terminal to start Zookeeper and Kafka.")

def uninstall_kafka():
    """Uninstall Apache Kafka using the unified package manager script."""
    speak("Uninstalling Apache Kafka now.")
    clear_metadata = get_confirmation_for_metadata_clear()
    if execute_shell_script('pkgInstaller.sh', 'uninstall', 'kafka', clear_metadata):
        speak("Apache Kafka has been uninstalled successfully.")

def run_kafka():
    """Starts Zookeeper and Kafka Broker."""
    speak("Attempting to start Zookeeper and Kafka Broker.")
    # Execute the kafka_utils.sh script with the 'start' argument
    if execute_shell_script('kafka_utils.sh', 'start'):
        speak("Zookeeper and Kafka Broker started successfully.")
    else:
        speak("Failed to start Zookeeper and Kafka Broker. Please check the logs for details.")


def main():
    """Main function to run the assistant"""
    speak("Hello! I am Shree, your voice assistant. How can I help you today?")
    
    while True:
        query = takeCommand()
        
        # If voice command is not understood, prompt for typed input
        if query == "None":
            speak("I didn't understand your voice command. Please type your command, or say 'exit' to quit.")
            print("Please type your command (e.g., 'install git', 'uninstall vscode', 'do github connection', 'install kafka', 'run kafka', 'exit'):")
            typed_query = input().strip().lower()
            if not typed_query: # If user just pressed enter
                continue
            query = typed_query # Use the typed query for processing
        
        # Prioritize uninstall commands to avoid misinterpretation
        if 'uninstall git' in query:
            uninstall_git()
        elif 'install git' in query:
            install_git()
        elif 'check git config' in query or 'check git configuration' in query:
            check_git_configuration()
        elif 'generate ssh key' in query or 'create ssh key' in query:
            generate_and_display_ssh_key()
        elif 'show ssh key' in query or 'display ssh key' in query:
            execute_shell_script('git_utils.sh', 'display_ssh')
        elif 'guide github connection' in query or 'github ssh guide' in query:
            guide_github_connection()
        elif 'check github connection' in query or 'check ssh connection' in query:
            check_github_ssh_connection()
        elif 'do github connection' in query or 'setup git configuration' in query or 'set up git' in query: # Both commands now trigger the full flow
            do_github_connection_flow()
        
        elif 'uninstall java' in query or 'uninstall jdk' in query:
            uninstall_jdk()
        elif 'install java' in query or 'install jdk' in query:
            install_jdk()
        
        elif 'uninstall vs code' in query or 'uninstall visual studio code' in query:
            uninstall_vscode()
        elif 'install vs code' in query or 'install visual studio code' in query:
            install_vscode()
        
        elif 'uninstall android studio' in query:
            uninstall_android_studio()
        elif 'install android studio' in query:
            install_android_studio()

        elif 'uninstall neovim' in query:
            uninstall_neovim()
        elif 'install neovim' in query:
            install_neovim()
        
        elif 'uninstall neofetch' in query:
            uninstall_neofetch()
        elif 'install neofetch' in query:
            install_neofetch()

        elif 'uninstall snap' in query or 'uninstall snapd' in query:
            uninstall_snap()
        elif 'install snap' in query or 'install snapd' in query:
            install_snap()
        
        elif 'uninstall wireshark' in query:
            uninstall_wireshark()
        elif 'install wireshark' in query:
            install_wireshark()
        
        elif 'uninstall kafka' in query or 'uninstall apache kafka' in query:
            uninstall_kafka()
        elif 'install kafka' in query or 'install apache kafka' in query:
            install_kafka()
        elif 'run kafka' in query or 'start kafka' in query: # New command
            run_kafka()

        elif 'exit' in query or 'quit' in query or 'goodbye' in query:
            speak("Goodbye! Have a nice day!")
            break
        
        else:
            speak("I didn't understand that command. Please try again.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
        speak("Goodbye!")
    except Exception as e:
        logger.critical(f"Critical error: {e}")
        print(f"Critical error occurred: {e}")
        speak("I encountered a critical error and need to shut down. Please check the logs.")
