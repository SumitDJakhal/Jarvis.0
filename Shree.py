#!/usr/bin/env python3
# Ubuntu Linux Voice Assistant - Shree

import speech_recognition as sr  # Speech recognition
import subprocess
import os
import logging
from gtts import gTTS  # Google Text-to-Speech
from dotenv import load_dotenv  # For secure env variables
import time # Import time for delays
import select # For non-blocking read on subprocess pipes
import webbrowser # Added for opening websites
import datetime # Added for timestamps in history
from urllib.parse import quote_plus # Added for URL encoding search queries

# PyQt5 Imports for UI
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QTextEdit, QLabel, QFrame, QMessageBox, QDialog,
    QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QEventLoop
from PyQt5.QtGui import QColor, QPalette, QIcon, QFont

# Set up main application logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("shree.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("shree")

# Set up a separate logger for command history
history_logger = logging.getLogger("command_history")
history_logger.setLevel(logging.INFO)
# Clear existing handlers to prevent duplicate logging
if history_logger.handlers:
    for handler in history_logger.handlers:
        history_logger.removeHandler(handler)
history_handler = logging.FileHandler("command_history.log")
history_formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
history_handler.setFormatter(history_formatter)
history_logger.addHandler(history_handler)
history_logger.propagate = False # Prevent history logs from going to the main logger

# Load environment variables from .env file
load_dotenv()

# --- Global Signal Handler (for communication from worker threads and global functions to UI) ---
class GlobalSignaller(QObject):
    ui_update_signal = pyqtSignal(str, str) # (sender, message)
    show_help_signal = pyqtSignal() # New signal to request showing the help dialog

# Create a single global instance of the signaller
global_signals = GlobalSignaller()

# --- Global Signal for Blocking UI Confirmation (e.g., metadata clear) ---
class BlockingConfirmationSignaller(QObject):
    request_blocking_dialog = pyqtSignal(str) # Argument: Message to display in dialog
    dialog_response = pyqtSignal(str) # Argument: result_string ("yes" to clear metadata, "no" to keep metadata)

global_confirmation_signals = BlockingConfirmationSignaller()

# --- Worker Thread for Long-Running Tasks ---
class WorkerThread(QThread):
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._running_task = None

    def run(self):
        pass # Task is executed directly by self.execute_task()

    def set_task(self, func, args):
        """Sets the task for the worker thread to execute."""
        self._running_task = (func, args)
        if not self.isRunning():
            self.start()

    def execute_task(self):
        """Executes the set task and signals completion."""
        if self._running_task:
            func, args = self._running_task
            try:
                func(*args)
            except Exception as e:
                logger.error(f"Error in worker thread task {func.__name__}: {e}")
                global_signals.ui_update_signal.emit("Shree", f"An internal error occurred during processing: {e}")
            finally:
                self._running_task = None
                self.finished.emit() # Signal that the task is done

# --- Voice Assistant Core Functions (modified to interact with UI via global_signals) ---

def speak(text):
    """Convert text to speech using gTTS and update UI."""
    logger.info(f"Speaking: {text}")
    global_signals.ui_update_signal.emit("Shree", text) # Update UI conversation log via global signal

    try:
        tts = gTTS(text=text, lang='en')
        tts.save("output.mp3")
        
        try:
            subprocess.run(['mpg123', "-q", "output.mp3"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            logger.error("mpg123 not found. Please install it (e.g., sudo apt install mpg123).")
            global_signals.ui_update_signal.emit("Shree", "Error: mpg123 not found. Cannot play audio.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error playing audio with mpg123: {e}")
            global_signals.ui_update_signal.emit("Shree", f"Error playing audio: {e}")
        finally:
            if os.path.exists("output.mp3"):
                os.remove("output.mp3")
    except Exception as e:
        logger.error(f"Error in speak function: {e}")
        global_signals.ui_update_signal.emit("Shree", f"An error occurred while speaking: {e}")

def takeCommand_for_ui():
    """Take microphone input from the user and return string output, updating UI status."""
    global shree_app_instance # Access the main application instance
    if shree_app_instance:
        shree_app_instance.toggle_mic_status(True) # Turn on mic indicator in UI
    
    r = sr.Recognizer()
    query = "None"
    try:
        global_signals.ui_update_signal.emit("Shree", "Listening...")
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.5)
            r.pause_threshold = 1
            audio = r.listen(source, timeout=5, phrase_time_limit=5)
        
        global_signals.ui_update_signal.emit("Shree", "Recognizing...")
        query = r.recognize_google(audio, language='en-in')
        global_signals.ui_update_signal.emit("You", f"(Voice) {query}")
        return query.lower()
    
    except sr.WaitTimeoutError:
        logger.info("Timeout occurred while listening")
        global_signals.ui_update_signal.emit("Shree", "I didn't catch that. Could you repeat?")
        return "None"
    except sr.UnknownValueError:
        logger.info("Could not understand audio")
        global_signals.ui_update_signal.emit("Shree", "I didn't catch that. Could you repeat?")
        return "None"
    except sr.RequestError as e:
        logger.error(f"Google Speech Recognition service error: {e}")
        global_signals.ui_update_signal.emit("Shree", f"Speech service error: {e}")
        return "None"
    except Exception as e:
        logger.error(f"Error in takeCommand_for_ui: {e}")
        global_signals.ui_update_signal.emit("Shree", f"An unexpected error occurred during voice input: {e}")
        return "None"
    finally:
        if shree_app_instance:
            shree_app_instance.toggle_mic_status(False) # Turn off mic indicator

# --- Helper functions (using UI for confirmation) ---

def get_confirmation_for_metadata_clear():
    """
    Asks the user for confirmation to keep or remove metadata via a UI dialog.
    This function will block the worker thread until a response is received from the UI.
    Returns 'yes' to pkgInstaller.sh if metadata should be removed (user typed 'no' to keep).
    Returns 'no' to pkgInstaller.sh if metadata should be kept (user typed 'yes' to keep).
    Default is to remove metadata if no valid input is given.
    """
    logger.info("Requesting UI confirmation for metadata clearance.")
    
    # Text to display in the QMessageBox
    dialog_message = "Would you like to KEEP associated configuration files and metadata for this application?\n\n" \
                     "Click 'Yes' to keep metadata.\n" \
                     "Click 'No' to remove metadata."

    # Emit signal to main UI thread to show the blocking dialog
    global_confirmation_signals.request_blocking_dialog.emit(dialog_message)

    # Use a QEventLoop to temporarily block this worker thread
    # until the UI responds via dialog_response signal.
    loop = QEventLoop()
    
    # Initialize confirmation_result with the default (remove metadata)
    # Default is "yes" for pkgInstaller.sh (meaning clear metadata)
    confirmation_result = "yes" 
    
    def on_dialog_response(response_string):
        nonlocal confirmation_result
        confirmation_result = response_string
        loop.quit()

    # Connect the response signal to quit the loop.
    # We ensure this connection is made and disconnected cleanly.
    global_confirmation_signals.dialog_response.connect(on_dialog_response)
    
    # Run the event loop; this blocks the current thread until loop.quit() is called.
    loop.exec_()
    
    # Disconnect to prevent multiple connections if this function is called again
    try:
        global_confirmation_signals.dialog_response.disconnect(on_dialog_response)
    except TypeError: # Disconnect may fail if signal was already disconnected (e.g. by previous attempt)
        pass

    logger.info(f"UI confirmation result: {confirmation_result}")
    return confirmation_result # This is 'yes' (clear) or 'no' (keep) for pkgInstaller.sh

def execute_shell_script(script_name, *args):
    """
    Helper function to execute any shell script, relying on system's sudo password prompt
    and streaming output to the UI in real-time.
    """
    script_path = None
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
        subprocess.run(chmod_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) # No need to capture output for chmod
        
        # Build the command list
        command = ['bash', script_path] + list(args)

        # Determine if sudo is required
        # Note: We now rely on the system's sudo prompt, not our custom UI one.
        requires_sudo_password = False
        if any(arg in command for arg in ['install', 'uninstall']) and script_name in ['pkgInstaller.sh', 'git_utils.sh', 'kafka_utils.sh']:
            # Assume these operations usually require sudo
            requires_sudo_password = True
        
        if requires_sudo_password:
            full_command = ['sudo'] + command # Let sudo handle its own password prompt
        else:
            full_command = command

        logger.info(f"Executing: {' '.join(full_command)}")
        global_signals.ui_update_signal.emit("Shree", "System might prompt for sudo password in the terminal or a graphical dialog. Please enter it there to continue.")
        
        # Start the subprocess
        process = subprocess.Popen(
            full_command,
            stdin=subprocess.DEVNULL, # Sudo will manage its own stdin for password
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True, # For text input/output
            bufsize=1 # Line-buffered output for real-time streaming
        )

        # --- Stream output in real-time ---
        pipes = [process.stdout, process.stderr]
        stdout_buffer = [] # Not strictly needed for streaming, but good for debugging if process fails later
        stderr_buffer = []

        while process.poll() is None or pipes:
            rlist, _, _ = select.select(pipes, [], [], 0.1) # Timeout to keep UI responsive

            for fd in rlist:
                line = fd.readline()
                if line:
                    if fd == process.stdout:
                        global_signals.ui_update_signal.emit("System Output", line.strip())
                        stdout_buffer.append(line)
                    elif fd == process.stderr:
                        global_signals.ui_update_signal.emit("System Error", line.strip())
                        stderr_buffer.append(line)
                else: # EOF, pipe closed
                    if fd in pipes:
                        pipes.remove(fd)

            # After reading available data, if process has finished, read any remaining data
            if process.poll() is not None and not pipes:
                remaining_stdout = process.stdout.read()
                if remaining_stdout:
                    global_signals.ui_update_signal.emit("System Output", remaining_stdout.strip())
                    stdout_buffer.append(remaining_stdout)
                remaining_stderr = process.stderr.read()
                if remaining_stderr:
                    global_signals.ui_update_signal.emit("System Error", remaining_stderr.strip())
                    stderr_buffer.append(remaining_stderr)
                break 

        return_code = process.returncode # Get final return code

        if return_code != 0:
            global_signals.ui_update_signal.emit("Shree", f"Command failed with exit code {return_code}.")
            return False

        return True

    except Exception as e:
        logger.error(f"An unexpected error occurred during {script_name} execution: {e}")
        global_signals.ui_update_signal.emit("Shree", f"An unexpected error occurred while running {script_name}. Please check the logs.")
        return False

# --- New Website Handling Functions ---
def _open_website(url, website_name):
    """Opens a website in the default system browser in a new tab and updates UI."""
    logger.info(f"Attempting to open {website_name} at: {url}")
    global_signals.ui_update_signal.emit("Shree", f"Opening {website_name} in your default browser...")
    try:
        webbrowser.open_new_tab(url)
        speak(f"{website_name} has been opened.")
    except Exception as e:
        logger.error(f"Error opening {website_name}: {e}")
        speak(f"Sorry, I could not open {website_name}. An error occurred: {e}")

# --- Wrapped functions for commands ---
def install_git():
    speak("Installing Git now.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'git'):
        speak("Git has been installed successfully.")

def uninstall_git():
    speak("Uninstalling Git now.")
    clear_metadata_choice = get_confirmation_for_metadata_clear() # 'yes' (clear) or 'no' (keep)
    script_success = execute_shell_script('pkgInstaller.sh', 'uninstall', 'git', clear_metadata_choice)
    
    if script_success:
        metadata_action_text = "removed" if clear_metadata_choice == "yes" else "kept"
        speak(f"Git has been uninstalled successfully, and its associated metadata was {metadata_action_text}.")
    else:
        speak("Git uninstallation failed.")


def check_git_configuration():
    speak("Checking your Git user configuration.")
    execute_shell_script('git_utils.sh', 'check_config')

def generate_and_display_ssh_key():
    speak("To generate an SSH key, I need your email address for the key comment.")
    global_signals.ui_update_signal.emit("Shree", "Please type your email for the SSH key comment (e.g., 'your_email@example.com'):")
    # For UI input, we would typically use a QInputDialog or a dedicated input field.
    # For now, this will block and wait for console input if the voice fails to provide it.
    user_email = input().strip()
    if not user_email:
        speak("No email provided. SSH key generation aborted.")
        return
    
    speak("Generating and displaying your SSH key now.")
    execute_shell_script('git_utils.sh', 'gen_ssh', user_email)
    execute_shell_script('git_utils.sh', 'display_ssh')

def guide_github_connection():
    speak("I will now guide you on how to add your SSH key to GitHub.")
    execute_shell_script('git_utils.sh', 'guide_github')

def check_github_ssh_connection():
    speak("Checking your SSH connection to GitHub.")
    execute_shell_script('git_utils.sh', 'check_conn')

def do_github_connection_flow():
    speak("Starting the GitHub connection setup flow.")
    execute_shell_script('git_utils.sh', 'do_github_connection_flow')

def install_jdk():
    valid_versions = ["11", "17", "21"]
    jdk_version = None
    
    speak("Which OpenJDK version would you like to install? For example, you can say 11, 17, or 21.")
    
    version_obtained = False
    for i in range(3):
        if not version_obtained:
            speak(f"Attempt {i+1} for voice input.")
            query = takeCommand_for_ui()
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
            # This would ideally be a UI text input pop-up
            typed_choice = takeCommand_for_ui() # Still using voice to get choice
            if "yes" in typed_choice:
                global_signals.ui_update_signal.emit("Shree", "Please type the JDK version (e.g., 11, 17, 21): ")
                typed_version = input().strip() # Still console input for now
                if typed_version in valid_versions:
                    jdk_version = typed_version
                    version_obtained = True
                    break
                else:
                    speak("Invalid version typed. Let's try voice again.")
            elif "no" in typed_choice:
                speak("Okay, trying voice again.")
            else:
                speak("I didn't understand your choice. Let's try voice again.")

    if not version_obtained:
        speak("I'm having trouble getting the JDK version. Aborting JDK installation.")
        return

    if jdk_version not in valid_versions:
        speak(f"The version {jdk_version} is not a common LTS version I can install. Please choose from {', '.join(valid_versions)}.")
        return

    confirmed = False
    for i in range(3):
        speak(f"You said version {jdk_version}. Is that correct? Say yes or no.")
        confirmation_query = takeCommand_for_ui()

        if "yes" in confirmation_query:
            confirmed = True
            break
        elif "no" in confirmation_query:
            speak("Okay, let's restart the version selection process.")
            speak("Installation aborted as you indicated the version was incorrect.")
            return
        else:
            speak("I didn't understand your confirmation. Please say 'yes' or 'no' again.")
    if not confirmed:
        speak("Could not confirm JDK version. Aborting installation.")
        return

    speak(f"Okay, I will now attempt to install OpenJDK version {jdk_version}. This may require your sudo password.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'jdk', jdk_version):
        speak(f"OpenJDK version {jdk_version} installed successfully.")
        speak("Environment variables for Java are typically set by the system after installation, or you might need to restart your terminal.")

def uninstall_jdk():
    valid_versions = ["11", "17", "21"]
    jdk_version = None
    
    speak("Which OpenJDK version would you like to uninstall? For example, you can say 11, 17, or 21.")

    version_obtained = False
    for i in range(3):
        if not version_obtained:
            speak(f"Attempt {i+1} for voice input.")
            query = takeCommand_for_ui()
            if query != "None":
                found_versions = [v for v in query if v in valid_versions]
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
            typed_choice = takeCommand_for_ui()
            if "yes" in typed_choice:
                global_signals.ui_update_signal.emit("Shree", "Please type the JDK version (e.g., 11, 17, 21): ")
                typed_version = input().strip()
                if typed_version in valid_versions:
                    jdk_version = typed_version
                    version_obtained = True
                    break
                else:
                    speak("Invalid version typed. Let's try voice again.")
            elif "no" in typed_choice:
                speak("Okay, trying voice again.")
            else:
                speak("I didn't understand your choice. Let's try voice again.")

    if not version_obtained:
        speak("I'm having trouble getting the JDK version. Aborting JDK uninstallation.")
        return

    if jdk_version not in valid_versions:
        speak(f"The version {jdk_version} is not a common LTS version I can uninstall. Please choose from {', '.join(valid_versions)}.")
        return

    speak(f"Okay, I will now attempt to uninstall OpenJDK version {jdk_version}. This may require your sudo password.")
    clear_metadata_choice = get_confirmation_for_metadata_clear()
    script_success = execute_shell_script('pkgInstaller.sh', 'uninstall', 'jdk', jdk_version, clear_metadata_choice)
    
    if script_success:
        metadata_action_text = "removed" if clear_metadata_choice == "yes" else "kept"
        speak(f"OpenJDK version {jdk_version} has been uninstalled successfully, and its associated metadata was {metadata_action_text}.")
    else:
        speak("OpenJDK uninstallation failed.")


def install_vscode():
    speak("Installing Visual Studio Code now.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'vscode'):
        speak("Visual Studio Code has been installed successfully.")

def uninstall_vscode():
    speak("Uninstalling Visual Studio Code now.")
    clear_metadata_choice = get_confirmation_for_metadata_clear()
    script_success = execute_shell_script('pkgInstaller.sh', 'uninstall', 'vscode', clear_metadata_choice)
    
    if script_success:
        metadata_action_text = "removed" if clear_metadata_choice == "yes" else "kept"
        speak(f"Visual Studio Code has been uninstalled successfully, and its associated metadata was {metadata_action_text}.")
    else:
        speak("Visual Studio Code uninstallation failed.")

def install_android_studio():
    speak("Installing Android Studio now.")
    speak("This will download a large file and may take a while.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'android_studio'):
        speak("Android Studio installation process completed. Remember to log out and log back in for KVM group changes to take effect.")

def uninstall_android_studio():
    speak("Uninstalling Android Studio now.")
    clear_metadata_choice = get_confirmation_for_metadata_clear()
    script_success = execute_shell_script('pkgInstaller.sh', 'uninstall', 'android_studio', clear_metadata_choice)
    
    if script_success:
        metadata_action_text = "removed" if clear_metadata_choice == "yes" else "kept"
        speak(f"Android Studio has been uninstalled successfully, and its associated metadata was {metadata_action_text}.")
    else:
        speak("Android Studio uninstallation failed.")

def install_neovim():
    speak("Installing Neovim now.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'neovim'):
        speak("Neovim has been installed successfully.")

def uninstall_neovim():
    speak("Uninstalling Neovim now.")
    clear_metadata_choice = get_confirmation_for_metadata_clear()
    script_success = execute_shell_script('pkgInstaller.sh', 'uninstall', 'neovim', clear_metadata_choice)
    
    if script_success:
        metadata_action_text = "removed" if clear_metadata_choice == "yes" else "kept"
        speak(f"Neovim has been uninstalled successfully, and its associated metadata was {metadata_action_text}.")
    else:
        speak("Neovim uninstallation failed.")

def install_neofetch():
    speak("Installing Neofetch now.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'neofetch'):
        speak("Neofetch has been installed successfully.")

def uninstall_neofetch():
    speak("Uninstalling Neofetch now.")
    clear_metadata_choice = get_confirmation_for_metadata_clear()
    script_success = execute_shell_script('pkgInstaller.sh', 'uninstall', 'neofetch', clear_metadata_choice)
    
    if script_success:
        metadata_action_text = "removed" if clear_metadata_choice == "yes" else "kept"
        speak(f"Neofetch has been uninstalled successfully, and its associated metadata was {metadata_action_text}.")
    else:
        speak("Neofetch uninstallation failed.")

def install_snap():
    speak("Installing Snapd now.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'snap'):
        speak("Snapd has been installed successfully.")

def uninstall_snap():
    speak("Uninstalling Snapd now.")
    clear_metadata_choice = get_confirmation_for_metadata_clear()
    script_success = execute_shell_script('pkgInstaller.sh', 'uninstall', 'snap', clear_metadata_choice)
    
    if script_success:
        metadata_action_text = "removed" if clear_metadata_choice == "yes" else "kept"
        speak(f"Snapd has been uninstalled successfully, and its associated metadata was {metadata_action_text}.")
    else:
        speak("Snapd uninstallation failed.")

def install_wireshark():
    speak("Installing Wireshark now.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'wireshark'):
        speak("Wireshark has been installed successfully.")
        speak("Remember to log out and log back in for group changes to take effect and to capture packets without sudo.")

def uninstall_wireshark():
    speak("Uninstalling Wireshark now.")
    clear_metadata_choice = get_confirmation_for_metadata_clear()
    script_success = execute_shell_script('pkgInstaller.sh', 'uninstall', 'wireshark', clear_metadata_choice)
    
    if script_success:
        metadata_action_text = "removed" if clear_metadata_choice == "yes" else "kept"
        speak(f"Wireshark has been uninstalled successfully, and its associated metadata was {metadata_action_text}.")
    else:
        speak("Wireshark uninstallation failed.")

def install_kafka():
    speak("Installing Apache Kafka now.")
    if execute_shell_script('pkgInstaller.sh', 'install', 'kafka'):
        speak("Apache Kafka installation process initiated. Please follow the instructions in the terminal to start Zookeeper and Kafka.")

def uninstall_kafka():
    speak("Uninstalling Apache Kafka now.")
    clear_metadata_choice = get_confirmation_for_metadata_clear()
    script_success = execute_shell_script('pkgInstaller.sh', 'uninstall', 'kafka', clear_metadata_choice)
    
    if script_success:
        metadata_action_text = "removed" if clear_metadata_choice == "yes" else "kept"
        speak(f"Apache Kafka has been uninstalled successfully, and its associated metadata was {metadata_action_text}.")
    else:
        speak("Apache Kafka uninstallation failed.")

def run_kafka():
    speak("Attempting to start Zookeeper and Kafka Broker.")
    if execute_shell_script('kafka_utils.sh', 'start'):
        speak("Zookeeper and Kafka Broker started successfully.")
    else:
        speak("Failed to start Zookeeper and Kafka Broker. Please check the logs for details.")

# --- Help Command ---
def show_help():
    """Triggers the display of the help dialog."""
    global_signals.show_help_signal.emit()

# --- Command Processing ---
def process_command(query_text):
    """Processes a command string and logs it to history."""
    # Log the command to history before processing
    history_logger.info(query_text)

    query = query_text.lower()
    logger.info(f"Processing command: {query}")
    global_signals.ui_update_signal.emit("Shree", f"Processing command: '{query_text}'...") # Indicate processing

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
    elif 'do github connection' in query or 'setup git configuration' in query or 'set up git' in query:
        do_github_connection_flow()
    
    elif 'uninstall java' in query or 'uninstall jdk' in query:
        uninstall_jdk()
    elif 'install java' in query or 'install jdk' in query:
        install_jdk()
    
    elif 'uninstall vs code' in query or 'uninstall visual studio code' in query:
        uninstall_vscode()
    elif 'install vs code' in query:
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
    elif 'run kafka' in query or 'start kafka' in query:
        run_kafka()
    
    # --- Website Handling Commands ---
    elif 'open google' in query:
        speak("What would you like to search for on Google?")
        global_signals.ui_update_signal.emit("Shree", "What would you like to search for on Google? (Type your query or speak after the beep)")
        google_query = takeCommand_for_ui()
        if google_query and google_query != 'None':
            encoded_query = quote_plus(google_query)
            search_url = f"https://www.google.com/search?q={encoded_query}"
            _open_website(search_url, f"Google with query: '{google_query}'")
        else:
            speak("No search query provided. Opening Google homepage.")
            _open_website("https://www.google.com", "Google")
    elif 'open youtube' in query:
        speak("What would you like to search for on YouTube?")
        global_signals.ui_update_signal.emit("Shree", "What would you like to search for on YouTube? (Type your query or speak after the beep)")
        youtube_query = takeCommand_for_ui()
        if youtube_query and youtube_query != 'None':
            encoded_query = quote_plus(youtube_query)
            search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
            _open_website(search_url, f"YouTube with query: '{youtube_query}'")
        else:
            speak("No search query provided. Opening YouTube homepage.")
            _open_website("https://www.youtube.com", "YouTube")
    elif 'open wikipedia' in query:
        speak("What would you like to search for on Wikipedia?")
        global_signals.ui_update_signal.emit("Shree", "What would you like to search for on Wikipedia? (Type your query or speak after the beep)")
        wikipedia_query = takeCommand_for_ui()
        if wikipedia_query and wikipedia_query != 'None':
            encoded_query = quote_plus(wikipedia_query)
            search_url = f"https://en.wikipedia.org/wiki/Special:Search?search={encoded_query}"
            _open_website(search_url, f"Wikipedia with query: '{wikipedia_query}'")
        else:
            speak("No search query provided. Opening Wikipedia homepage.")
            _open_website("https://www.wikipedia.org", "Wikipedia")
    elif 'open github' in query:
        speak("What would you like to search for on GitHub?")
        global_signals.ui_update_signal.emit("Shree", "What would you like to search for on GitHub? (Type your query or speak after the beep)")
        github_query = takeCommand_for_ui()
        if github_query and github_query != 'None':
            encoded_query = quote_plus(github_query)
            search_url = f"https://github.com/search?q={encoded_query}"
            _open_website(search_url, f"GitHub with query: '{github_query}'")
        else:
            speak("No search query provided. Opening GitHub homepage.")
            _open_website("https://github.com", "GitHub")
    elif 'open gitlab' in query:
        speak("What would you like to search for on GitLab?")
        global_signals.ui_update_signal.emit("Shree", "What would you like to search for on GitLab? (Type your query or speak after the beep)")
        gitlab_query = takeCommand_for_ui()
        if gitlab_query and gitlab_query != 'None':
            encoded_query = quote_plus(gitlab_query)
            search_url = f"https://gitlab.com/search?search={encoded_query}"
            _open_website(search_url, f"GitLab with query: '{gitlab_query}'")
        else:
            speak("No search query provided. Opening GitLab homepage.")
            _open_website("https://gitlab.com", "GitLab")
    
    elif 'help' in query or 'what can you do' in query or 'commands' in query: # New help command
        speak("Here are the commands I can help you with:")
        show_help()

    elif 'exit' in query or 'quit' in query or 'goodbye' in query:
        speak("Goodbye! Have a nice day!")
        QApplication.instance().quit() # Quit the QApplication
    
    else:
        speak("I didn't understand that command. Please try again.")

# --- PyQt5 GUI Application ---
class ShreeApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.worker_thread = WorkerThread()
        self.worker_thread.finished.connect(self.on_task_finished)
        # Connect the global signal instance's signal to a slot in the UI thread
        global_signals.ui_update_signal.connect(self.update_conversation_log)
        # Connect the new global confirmation request signal to a slot in ShreeApp
        global_confirmation_signals.request_blocking_dialog.connect(self._show_blocking_confirmation_dialog)
        global_signals.show_help_signal.connect(self._show_help_dialog) # Connect new help signal

    def initUI(self):
        self.setWindowTitle('Shree AI Assistant')
        self.setGeometry(100, 100, 800, 600) # x, y, width, height

        # Set overall dark theme and font
        self.setStyleSheet("""
            QWidget {
                background-color: #1a202c; /* shree-dark */
                color: #e2e8f0; /* shree-text */
                font-family: 'Inter', sans-serif;
                font-size: 14px;
            }
            QLabel#micStatusLabel {
                font-size: 16px;
                font-weight: 500;
                color: #e2e8f0;
                min-width: 120px; /* Ensure space for text */
            }
            QTextEdit {
                background-color: #2d3748; /* shree-light */
                border: 1px solid #667eea; /* shree-accent */
                border-radius: 8px;
                padding: 10px;
                selection-background-color: #667eea;
                selection-color: #ffffff;
            }
            QLineEdit {
                background-color: #2d3748;
                border: 1px solid #667eea;
                border-radius: 8px;
                padding: 10px;
                color: #e2e8f0;
            }
            QPushButton {
                background-color: #667eea; /* shree-accent */
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: #5a67d8; /* Darker accent on hover */
            }
            QPushButton:pressed {
                background-color: #4c51bf; /* Even darker accent on press */
            }
            QPushButton#micButton {
                background-color: #48bb78; /* shree-green */
            }
            QPushButton#micButton:hover {
                background-color: #38a169; /* Darker green */
            }
            QPushButton#micButton:pressed {
                background-color: #2f855a; /* Even darker green */
            }
            QPushButton#micButton.listening {
                background-color: #ef4444; /* shree-red when listening */
            }
            QPushButton#micButton.listening:hover {
                background-color: #dc2626; /* Darker red */
            }
        """)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Title Label
        title_label = QLabel('Shree AI Assistant')
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont("Inter", 28, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #667eea;") # shree-accent
        main_layout.addWidget(title_label)

        # Subtitle Label
        subtitle_label = QLabel('Your Personal Ubuntu Voice Assistant')
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #e2e8f0; opacity: 0.8;")
        main_layout.addWidget(subtitle_label)

        # Conversation Log
        self.conversation_log = QTextEdit()
        self.conversation_log.setReadOnly(True)
        self.conversation_log.setText("Shree: Hello! I am Shree, your voice assistant. How can I help you today?")
        main_layout.addWidget(self.conversation_log)

        # Input Area
        input_layout = QHBoxLayout()
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Type your command here...")
        self.user_input.returnPressed.connect(self.send_command) # Connect Enter key
        input_layout.addWidget(self.user_input)

        self.send_button = QPushButton('Send Command')
        self.send_button.clicked.connect(self.send_command)
        input_layout.addWidget(self.send_button)
        
        self.mic_button = QPushButton('Speak')
        self.mic_button.setObjectName("micButton") # For stylesheet targeting
        self.mic_button.setIcon(QIcon(':/icons/mic.png')) # Placeholder for a custom mic icon
        self.mic_button.clicked.connect(self.start_voice_input)
        input_layout.addWidget(self.mic_button)

        main_layout.addLayout(input_layout)

        # Control Buttons (Help, History)
        control_buttons_layout = QHBoxLayout()
        control_buttons_layout.setContentsMargins(0, 0, 0, 0) # No extra margins
        control_buttons_layout.setSpacing(10) # Spacing between buttons

        self.help_button = QPushButton('Help')
        self.help_button.clicked.connect(self._show_help_dialog)
        control_buttons_layout.addWidget(self.help_button)

        self.history_button = QPushButton('View History')
        self.history_button.clicked.connect(self._show_history_dialog)
        control_buttons_layout.addWidget(self.history_button)

        main_layout.addLayout(control_buttons_layout)


        # Mic Status Indicator
        self.mic_status_label = QLabel("Mic: Idle")
        self.mic_status_label.setObjectName("micStatusLabel")
        self.mic_status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        main_layout.addWidget(self.mic_status_label)

        self.setLayout(main_layout)

    def update_conversation_log(self, sender, message):
        """Appends messages to the conversation log."""
        current_text = self.conversation_log.toHtml() # Use HTML for rich text/styling
        # Add a span with font-weight for sender, and append message
        new_entry = f"<p><span style='font-weight: 600;'>{sender}:</span> {message}</p>"
        self.conversation_log.setHtml(current_text + new_entry)
        self.conversation_log.verticalScrollBar().setValue(self.conversation_log.verticalScrollBar().maximum()) # Scroll to bottom

    def toggle_mic_status(self, is_listening):
        """Updates the microphone status label and button style."""
        if is_listening:
            self.mic_status_label.setText("Mic: Listening...")
            self.mic_status_label.setStyleSheet("color: #48bb78;") # shree-green
            self.mic_button.setText("Listening...")
            self.mic_button.setStyleSheet("background-color: #ef4444;") # shree-red
            self.mic_button.setProperty("listening", True)
        else:
            self.mic_status_label.setText("Mic: Idle")
            self.mic_status_label.setStyleSheet("color: #e2e8f0;") # shree-text
            self.mic_button.setText("Speak")
            self.mic_button.setStyleSheet("background-color: #48bb78;") # shree-green
            self.mic_button.setProperty("listening", False)
        # Re-apply styles to ensure correct rendering after property change
        self.mic_button.style().polish(self.mic_button)


    def set_ui_busy(self, busy):
        """Sets the UI to a busy or idle state."""
        self.user_input.setEnabled(not busy)
        self.send_button.setEnabled(not busy)
        self.mic_button.setEnabled(not busy)
        self.help_button.setEnabled(not busy) # Disable help button
        self.history_button.setEnabled(not busy) # Disable history button

        if busy:
            self.mic_status_label.setText("Processing...")
            self.mic_status_label.setStyleSheet("color: #667eea;") # Accent color for processing
        else:
            self.mic_status_label.setText("Mic: Idle")
            self.mic_status_label.setStyleSheet("color: #e2e8f0;")


    def send_command(self):
        """Handles sending text commands from the input field."""
        command = self.user_input.text().strip()
        if command:
            self.update_conversation_log("You", command)
            self.user_input.clear()
            self.set_ui_busy(True) # Set UI to busy
            self.worker_thread.set_task(process_command, (command,))
            self.worker_thread.execute_task() # Trigger task execution in the worker thread

    def start_voice_input(self):
        """Starts the voice recognition process in a worker thread."""
        self.update_conversation_log("You", "Activating microphone...")
        self.set_ui_busy(True) # Set UI to busy
        self.worker_thread.set_task(self._run_voice_command, ())
        self.worker_thread.execute_task() # Trigger task execution in the worker thread

    def _run_voice_command(self):
        """Internal helper to call takeCommand_for_ui and then process the result."""
        voice_command = takeCommand_for_ui()
        if voice_command and voice_command != 'None':
            # update_conversation_log is called by takeCommand_for_ui
            process_command(voice_command)
        else:
            speak("No voice input received or understood.")

    def on_task_finished(self):
        """Slot to handle tasks finishing in the worker thread."""
        logger.info("Worker task finished.")
        self.set_ui_busy(False) # Set UI back to idle

    def _show_blocking_confirmation_dialog(self, message):
        """
        Displays a QMessageBox to get user confirmation for metadata,
        and emits the result back via a global signal.
        This runs on the main UI thread.
        """
        logger.info(f"Showing confirmation dialog: {message}")
        
        reply = QMessageBox.question(
            self,
            'Confirm Action', # Title of the dialog
            message,
            QMessageBox.Yes | QMessageBox.No, # Buttons: Yes, No
            QMessageBox.No # Default button: No (matches user's "no" to keep metadata, which means remove)
        )

        # Map QMessageBox reply to "yes" (clear metadata) or "no" (keep metadata) for the shell script
        # User clicks Yes (QMessageBox.Yes) -> means KEEP metadata -> pkgInstaller.sh gets 'no'
        # User clicks No (QMessageBox.No) -> means REMOVE metadata -> pkgInstaller.sh gets 'yes'
        result_for_script = "yes" if reply == QMessageBox.No else "no"
        
        # Emit the result back to the worker thread via the global signal
        global_confirmation_signals.dialog_response.emit(result_for_script)
        logger.info(f"User chose: {'No' if reply == QMessageBox.No else 'Yes'} (for keeping metadata). Emitting result: {result_for_script}")

    def _show_help_dialog(self):
        """Displays the help dialog."""
        help_dialog = HelpDialog(self)
        help_dialog.exec_() # Show dialog modally

    def _show_history_dialog(self):
        """Displays the command history dialog."""
        history_dialog = HistoryDialog(self)
        history_dialog.exec_() # Show dialog modally


# --- PyQt5 Help Dialog Class ---
class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Shree AI Assistant Commands")
        self.setGeometry(200, 200, 600, 500)
        self.setWindowModality(Qt.ApplicationModal) # Make it modal

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        title = QLabel("Available Commands")
        title.setFont(QFont("Inter", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #667eea; margin-bottom: 10px;")
        main_layout.addWidget(title)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content_widget = QWidget()
        scroll_area.setWidget(scroll_content_widget)
        
        commands_layout = QVBoxLayout(scroll_content_widget)
        commands_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        commands_layout.setSpacing(8)

        # Define commands and descriptions
        commands = {
            "install git": "Installs the Git version control system.",
            "uninstall git": "Uninstalls Git. Asks about keeping/removing metadata.",
            "check git config": "Checks your global Git user configuration (name and email).",
            "generate ssh key": "Generates a new SSH key for GitHub. You'll be prompted for an email.",
            "show ssh key": "Displays your public SSH key.",
            "guide github connection": "Provides instructions on how to add your SSH key to GitHub.",
            "check github connection": "Checks your SSH connection to GitHub.",
            "do github connection": "Walks you through the full GitHub SSH connection setup flow.",
            "install java <version>": "Installs OpenJDK. Replace <version> with 11, 17, or 21 (e.g., 'install java 17').",
            "uninstall java <version>": "Uninstalls OpenJDK. Replace <version> with 11, 17, or 21. Asks about metadata.",
            "install vs code": "Installs Visual Studio Code.",
            "uninstall vs code": "Uninstalls Visual Studio Code. Asks about keeping/removing metadata.",
            "install android studio": "Installs Android Studio. This may take a while.",
            "uninstall android studio": "Uninstalls Android Studio. Asks about keeping/removing metadata.",
            "install neovim": "Installs Neovim.",
            "uninstall neovim": "Uninstalls Neovim. Asks about keeping/removing metadata.",
            "install neofetch": "Installs Neofetch (a system information tool).",
            "uninstall neofetch": "Uninstalls Neofetch. Asks about keeping/removing metadata.",
            "install snap": "Installs Snapd (a universal packaging system).",
            "uninstall snap": "Uninstalls Snapd. Asks about keeping/removing metadata.",
            "install wireshark": "Installs Wireshark (a network protocol analyzer).",
            "uninstall wireshark": "Uninstalls Wireshark. Asks about keeping/removing metadata.",
            "install kafka": "Installs Apache Kafka. Requires manual steps to start services.",
            "uninstall kafka": "Uninstalls Apache Kafka. Asks about keeping/removing metadata.",
            "run kafka / start kafka": "Attempts to start Zookeeper and Kafka Broker services.",
            "open google": "Opens Google.com in your default browser. Will ask for a search query.",
            "open youtube": "Opens YouTube.com in your default browser. Will ask for a search query.",
            "open wikipedia": "Opens Wikipedia.org in your default browser. Will ask for a search query.",
            "open github": "Opens GitHub.com in your default browser. Will ask for a search query.",
            "open gitlab": "Opens GitLab.com in your default browser. Will ask for a search query.",
            "help": "Displays this list of commands.",
            "exit / quit / goodbye": "Closes the Shree AI Assistant application."
        }

        for cmd, desc in commands.items():
            cmd_label = QLabel(f"<b>{cmd}</b>")
            cmd_label.setFont(QFont("Inter", 12))
            cmd_label.setStyleSheet("color: #667eea;") # Accent color for command names
            commands_layout.addWidget(cmd_label)

            desc_label = QLabel(desc)
            desc_label.setFont(QFont("Inter", 11))
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #e2e8f0; margin-left: 15px; margin-bottom: 10px;")
            commands_layout.addWidget(desc_label)

        main_layout.addWidget(scroll_area)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept) # Close the dialog
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #667eea;
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #5a67d8;
            }
        """)
        main_layout.addWidget(close_button)

# --- New Command History Dialog Class ---
class HistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Shree AI Assistant - Command History")
        self.setGeometry(250, 250, 700, 500)
        self.setWindowModality(Qt.ApplicationModal)

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        title = QLabel("Command History")
        title.setFont(QFont("Inter", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #667eea; margin-bottom: 10px;")
        main_layout.addWidget(title)

        self.history_display = QTextEdit()
        self.history_display.setReadOnly(True)
        self.history_display.setStyleSheet("""
            background-color: #2d3748;
            border: 1px solid #667eea;
            border-radius: 8px;
            padding: 10px;
            color: #e2e8f0;
        """)
        main_layout.addWidget(self.history_display)

        self._load_history() # Load history when the dialog is initialized

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #667eea;
                color: white;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #5a67d8;
            }
        """)
        main_layout.addWidget(close_button)

    def _load_history(self):
        """Reads and displays the command history from the log file."""
        history_content = []
        history_file_path = "command_history.log"
        if os.path.exists(history_file_path):
            try:
                with open(history_file_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            # Assuming format: YYYY-MM-DD HH:MM:SS - Command Text
                            parts = line.split(' - ', 1) # Split only on the first occurrence of ' - '
                            if len(parts) == 2:
                                timestamp_str, command_text = parts
                                # Format for display, e.g., "<b>[Timestamp]</b>: Command Text"
                                history_content.append(f"<p><span style='font-weight: 600; color: #9be8ff;'>[{timestamp_str}]</span>: {command_text}</p>")
                            else:
                                history_content.append(f"<p>{line}</p>") # Fallback for malformed lines
            except Exception as e:
                logger.error(f"Error reading command history file: {e}")
                self.history_display.setText(f"Error loading history: {e}")
                return
        else:
            history_content.append("<p>No command history available yet.</p>")

        self.history_display.setHtml("".join(history_content))
        self.history_display.verticalScrollBar().setValue(self.history_display.verticalScrollBar().maximum()) # Scroll to bottom


# --- Main Application Entry Point ---
shree_app_instance = None # Global reference to the app instance

if __name__ == '__main__':
    app = QApplication([])

    # Set system palette for a dark theme baseline if default is not dark
    app.setStyle("Fusion") # 'Fusion' is a good cross-platform style
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(26, 32, 44))
    palette.setColor(QPalette.WindowText, QColor(226, 232, 240))
    palette.setColor(QPalette.Base, QColor(45, 55, 72))
    palette.setColor(QPalette.AlternateBase, QColor(30, 36, 48))
    palette.setColor(QPalette.ToolTipBase, QColor(26, 32, 44))
    palette.setColor(QPalette.ToolTipText, QColor(226, 232, 240))
    palette.setColor(QPalette.Text, QColor(226, 232, 240))
    palette.setColor(QPalette.Button, QColor(102, 126, 234))
    palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Link, QColor(102, 126, 234))
    palette.setColor(QPalette.Highlight, QColor(102, 126, 234))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)


    shree_app_instance = ShreeApp()
    shree_app_instance.show()

    # Initial greeting
    speak("Hello! I am Shree, your voice assistant. How can I help you today?")

    try:
        exit_code = app.exec_() # Start the Qt event loop
        os._exit(exit_code) # Ensure clean exit
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
        speak("Goodbye!")
        os._exit(0)
    except Exception as e:
        logger.critical(f"Critical error: {e}")
        print(f"Critical error occurred: {e}")
        speak("I encountered a critical error and need to shut down. Please check the logs.")
        os._exit(1)
