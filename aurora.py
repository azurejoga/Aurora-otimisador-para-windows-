import wx
import wx.adv
import subprocess
import pickle
import webbrowser
import ctypes
import os
import sys
import threading
import logging

# Log configuration
logging.basicConfig(filename='aurora.log', level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def is_admin():
    try:
        result = ctypes.windll.shell32.IsUserAnAdmin()
        if result:
            logging.info("User has admin privileges.")
        else:
            logging.info("User does not have admin privileges.")
        return result
    except OSError as e:
        logging.error("OS error occurred while checking admin privileges: %s", str(e))
        return False
    except Exception as e:
        logging.error("Unexpected error occurred: %s", str(e))
        return False

def run_as_admin():
    try:
        logging.info("Attempting to elevate privileges.")
        instance = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        if instance <= 32:
            logging.error("Failed to elevate privileges, ShellExecuteW returned %s", instance)
        else:
            logging.info("Privileges successfully elevated.")
    except Exception as e:
        logging.error("Error occurred while trying to elevate privileges: %s", e)

if not is_admin():
    run_as_admin()
    sys.exit()

# PowerShell command to enable script execution
powershell_command = "Set-ExecutionPolicy Unrestricted -Scope CurrentUser -Force"

# Runs PowerShell command
subprocess.run(["powershell", "-Command", powershell_command], shell=True, check=True)

class WelcomeDialog(wx.Dialog):
    def __init__(self, parent, id, title):
        super(WelcomeDialog, self).__init__(parent, id, title)

        panel = wx.Panel(self)

        # Welcome text in the dialog box
        welcome_text = wx.StaticText(panel, -1, "Hi, we're glad you want to try our program!")
        disclaimer_text = wx.StaticText(panel, -1, "Remember that all changes are made by you and we are not responsible for any issues.")
        restore_text = wx.StaticText(panel, -1, "Before doing anything, create a restore point on your PC to avoid any problems.")

        # "Ok, I want to continue" button in the dialog box
        ok_button = wx.Button(panel, label="Okay, I want to continue")
        ok_button.Bind(wx.EVT_BUTTON, self.on_ok)

        # Dialog box layout
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(welcome_text, 0, wx.ALL, 10)
        sizer.Add(disclaimer_text, 0, wx.ALL, 10)
        sizer.Add(restore_text, 0, wx.ALL, 10)
        sizer.Add(ok_button, 0, wx.CENTER | wx.ALL, 10)

        panel.SetSizer(sizer)

    def on_ok(self, event):
        self.EndModal(wx.ID_OK)

class MyFrame(wx.Frame):
    def __init__(self, parent, id, title):
        super(MyFrame, self).__init__(parent, id, title, size=(600, 400))

        panel = wx.Panel(self)

        # Command list
        self.lista_de_comandos = wx.ListCtrl(panel, -1, style=wx.LC_REPORT)
        self.lista_de_comandos.InsertColumn(0, "Name", width=150)
        self.lista_de_comandos.InsertColumn(1, "Description", width=250)
        self.lista_de_comandos.InsertColumn(2, "Command", width=300)
        self.lista_de_comandos.InsertColumn(3, "Type", width=100)

        # Create the "Add Commands" menu
        menu_bar = wx.MenuBar()
        file_menu = wx.Menu()
        add_command_item = file_menu.Append(wx.ID_ANY, "Add Commands", "Add a new command")
        self.Bind(wx.EVT_MENU, self.on_add_command, add_command_item)
        menu_bar.Append(file_menu, "Commands")

        # Create the "Tools" menu and add items
        tools_menu = wx.Menu()
        open_github_repo_item = tools_menu.Append(wx.ID_ANY, "Open GitHub Repository", "Open the repository on GitHub")
        download_latest_github_item = tools_menu.Append(wx.ID_ANY, "Download Latest Version", "Download Latest Version from GitHub")
        create_restore_point_item = tools_menu.Append(wx.ID_ANY, "Create Restore Point", "Create a system restore point")
        restore_changes_item = tools_menu.Append(wx.ID_ANY, "Restore Changes", "Restore system changes to the last restore point and restart")
        sort_commands_item = tools_menu.Append(wx.ID_ANY, "Sort Commands", "Sort commands alphabetically")
        check_updates_item = tools_menu.Append(wx.ID_ANY, "Check Updates", "Check for updates and close Aurora")

        # Bind the EVT_MENU event
        self.Bind(wx.EVT_MENU, self.open_github_repo, open_github_repo_item)
        self.Bind(wx.EVT_MENU, self.download_latest_github, download_latest_github_item)
        self.Bind(wx.EVT_MENU, self.create_system_restore_point, create_restore_point_item)
        self.Bind(wx.EVT_MENU, self.restore_changes, restore_changes_item)
        self.Bind(wx.EVT_MENU, self.sort_commands, sort_commands_item)
        self.Bind(wx.EVT_MENU, self.check_updates, check_updates_item)

        # Append the "Tools" menu to the menu bar
        menu_bar.Append(tools_menu, "Tools")
        self.SetMenuBar(menu_bar)

        # Layout
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.lista_de_comandos, 1, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(sizer)

        # Bind for Enter or Space key in the command list
        self.lista_de_comandos.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_execute_command)

        # Bind the EVT_CONTEXT_MENU event
        self.lista_de_comandos.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)

        # Load commands from the file
        self.commands = load_commands()

        # Populate the command list
        for command in self.commands:
            self.add_command_to_list(command)

    def on_execute_command(self, event):
        selected_item = self.lista_de_comandos.GetFirstSelected()
        if selected_item >= 0:
            cmd = self.lista_de_comandos.GetItemText(selected_item, col=2)
            type = self.lista_de_comandos.GetItemText(selected_item, col=3)

            # Execute the command in a separate thread
            threading.Thread(target=self.run_command, args=(cmd, type)).start()

    def on_add_command(self, event):
        # Open the dialog to add commands
        dlg = AddCommandDialog(self, -1, "Add Commands")
        result = dlg.ShowModal()
        if result == wx.ID_OK:
            name = dlg.name_text.GetValue()
            desc = dlg.desc_text.GetValue()
            cmd = dlg.cmd_text.GetValue()
            type = dlg.type_combo.GetValue()

            # Add the command to the list
            command = {"name": name, "desc": desc, "cmd": cmd, "type": type}
            self.commands.append(command)
            self.add_command_to_list(command)
            # Save the commands to the file
            save_commands(self.commands)

        dlg.Destroy()

    def add_command_to_list(self, command):
        index = self.lista_de_comandos.InsertItem(self.lista_de_comandos.GetItemCount(), command["name"])
        self.lista_de_comandos.SetItem(index, 1, command["desc"])
        self.lista_de_comandos.SetItem(index, 2, command["cmd"])
        self.lista_de_comandos.SetItem(index, 3, command["type"])

    def show_output_dialog(self, output):
        try:
            output_dialog = OutputDialog(self, -1, "Command Result", output)
            output_dialog.ShowModal()
        except Exception as e:
            logging.error("Error showing output dialog: %s", e)

    def show_notification(self, message, success=True):
        try:
            notification_title = "Success" if success else "Error"
            notification = wx.adv.NotificationMessage(title=notification_title, message=message, parent=None)
            notification.Show()
        except Exception as e:
            logging.error("Error showing notification: %s", e)

    def run_command(self, command, type):
        try:
            if "CMD" in type.upper():
                result = subprocess.run(["cmd", "/c", command], shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            elif "POWERSHELL" in type.upper():
                result = subprocess.run(["powershell", "-Command", command], shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            else:
                logging.error("Unsupported command type: %s", type)
                return

            if result.returncode == 0:
                wx.CallAfter(self.show_output_dialog, result.stdout)
                wx.CallAfter(self.show_notification, "Command executed successfully", success=True)
            else:
                wx.CallAfter(self.show_output_dialog, result.stderr)
                wx.CallAfter(self.show_notification, "Error executing command", success=False)

        except subprocess.CalledProcessError as e:
            wx.CallAfter(self.show_output_dialog, e.stderr)
            wx.CallAfter(self.show_notification, "Error executing command", success=False)
        except Exception as e:
            logging.error("Error executing command: %s", e)
            wx.CallAfter(self.show_output_dialog, "An unexpected error occurred")
            wx.CallAfter(self.show_notification, "An unexpected error occurred", success=False)

    def open_github_repo(self, event):
        github_url = "https://github.com/azurejoga/Aurora-Windows-Optimizer"
        webbrowser.open(github_url)

    def download_latest_github(self, event):
        download_url = "https://github.com/azurejoga/Aurora-Windows-Optimizer/releases"
        webbrowser.open(download_url)

    def create_system_restore_point(self, event):
        description = wx.GetTextFromUser("Enter a description for the restore point:", "Create Restore Point")
        if description:
            create_system_restore_point(description)

    def sort_commands(self, event):
        self.lista_de_comandos.DeleteAllItems()
        self.commands.sort(key=lambda x: x["name"])
        for command in self.commands:
            self.add_command_to_list(command)

    def create_context_menu(self):
        menu = wx.Menu()

        edit_item = wx.MenuItem(menu, wx.ID_ANY, "Edit")
        self.Bind(wx.EVT_MENU, self.on_edit_command, edit_item)
        menu.Append(edit_item)

        remove_item = wx.MenuItem(menu, wx.ID_ANY, "Remove Command")
        self.Bind(wx.EVT_MENU, self.on_remove_command, remove_item)
        menu.Append(remove_item)

        move_to_top_item = wx.MenuItem(menu, wx.ID_ANY, "Move to Top")
        self.Bind(wx.EVT_MENU, self.move_command_to_top, move_to_top_item)
        menu.Append(move_to_top_item)

        move_to_bottom_item = wx.MenuItem(menu, wx.ID_ANY, "Move to Bottom")
        self.Bind(wx.EVT_MENU, self.move_command_to_bottom, move_to_bottom_item)
        menu.Append(move_to_bottom_item)

        return menu

    def on_context_menu(self, event):
        selected_item = self.lista_de_comandos.GetFirstSelected()
        if selected_item >= 0:
            menu = self.create_context_menu()
            self.PopupMenu(menu)
            menu.Destroy()

    def on_edit_command(self, event):
        selected_item = self.lista_de_comandos.GetFirstSelected()
        if selected_item >= 0:
            name = self.lista_de_comandos.GetItemText(selected_item, col=0)
            desc = self.lista_de_comandos.GetItemText(selected_item, col=1)
            cmd = self.lista_de_comandos.GetItemText(selected_item, col=2)
            type = self.lista_de_comandos.GetItemText(selected_item, col=3)

            dlg = AddCommandDialog(self, -1, "Edit Command")
            dlg.name_text.SetValue(name)
            dlg.desc_text.SetValue(desc)
            dlg.cmd_text.SetValue(cmd)
            dlg.type_combo.SetValue(type)

            result = dlg.ShowModal()
            if result == wx.ID_OK:
                updated_name = dlg.name_text.GetValue()
                updated_desc = dlg.desc_text.GetValue()
                updated_cmd = dlg.cmd_text.GetValue()
                updated_type = dlg.type_combo.GetValue()

                self.lista_de_comandos.SetItem(selected_item, 0, updated_name)
                self.lista_de_comandos.SetItem(selected_item, 1, updated_desc)
                self.lista_de_comandos.SetItem(selected_item, 2, updated_cmd)
                self.lista_de_comandos.SetItem(selected_item, 3, updated_type)

                self.commands[selected_item] = {"name": updated_name, "desc": updated_desc, "cmd": updated_cmd, "type": updated_type}
                save_commands(self.commands)

            dlg.Destroy()

    def on_remove_command(self, event):
        selected_item = self.lista_de_comandos.GetFirstSelected()
        if selected_item >= 0:
            del self.commands[selected_item]
            self.lista_de_comandos.DeleteItem(selected_item)
            save_commands(self.commands)

    def check_updates(self, event):
        script_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
        update_exe_path_update = os.path.join(script_dir, "update", "update.exe")
        update_exe_path_same_folder = os.path.join(script_dir, "update.exe")

        if os.path.exists(update_exe_path_update):
            subprocess.run([update_exe_path_update], shell=True)
        elif os.path.exists(update_exe_path_same_folder):
            subprocess.run([update_exe_path_same_folder], shell=True)
        else:
            logging.error("update.exe not found.")

    def restore_changes(self, event):
        try:
            find_restore_point_command = "Get-ComputerRestorePoint | Sort-Object -Property CreationTime -Descending | Select-Object -First 1 | Format-List -Property CreationTime, Description, SequenceNumber"
            result = subprocess.run(["powershell", "-Command", find_restore_point_command], shell=True, capture_output=True, text=True)

            if result.returncode == 0:
                restore_point_info = result.stdout.strip()

                if restore_point_info:
                    restore_point_data = {line.split(':', 1)[0].strip(): line.split(':', 1)[1].strip() for line in restore_point_info.split('\n')}

                    dlg = wx.MessageDialog(None, f"Do you want to restore the system to the latest restore point?\n\n{restore_point_info}", "Restore Changes", wx.YES_NO | wx.ICON_QUESTION)
                    result = dlg.ShowModal()
                    dlg.Destroy()

                    if result == wx.ID_YES:
                        threading.Thread(target=self.perform_restoration, args=(restore_point_data,), daemon=True).start()
                else:
                    wx.MessageBox("Could not find a restore point. Create a restore point before attempting to restore changes.", "Restoration Error", wx.OK | wx.ICON_ERROR)
            else:
                wx.MessageBox(f"Error finding or restoring restore point:\n{result.stderr}", "Restoration Error", wx.OK | wx.ICON_ERROR)

        except subprocess.CalledProcessError as e:
            wx.MessageBox(f"Error executing PowerShell command:\n{e.stderr}", "Restoration Error", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.MessageBox(f"Unexpected error:\n{e}", "Restoration Error", wx.OK | wx.ICON_ERROR)

    def perform_restoration(self, restore_point_data):
        try:
            sequence_number = restore_point_data.get("SequenceNumber")
            restore_command = f"Restore-Computer -RestorePoint {sequence_number} -Confirm:$false"
            subprocess.run(["powershell", "-Command", restore_command], shell=True, check=True)

            wx.CallAfter(wx.MessageBox, f"Changes successfully restored to '{restore_point_data.get('Description')}' ({restore_point_data.get('CreationTime')})! The computer will be restarted.", "Restoration Completed", wx.OK | wx.ICON_INFORMATION)
            subprocess.run(["powershell", "Restart-Computer"])
        except subprocess.CalledProcessError as e:
            wx.CallAfter(wx.MessageBox, f"Error restoring changes:\n{e.stderr}", "Restoration Error", wx.OK | wx.ICON_ERROR)

    def move_command_to_top(self, event):
        selected_item = self.lista_de_comandos.GetFirstSelected()
        if selected_item > 0:
            self.commands.insert(0, self.commands.pop(selected_item))
            self.lista_de_comandos.DeleteAllItems()
            for command in self.commands:
                self.add_command_to_list(command)
            self.lista_de_comandos.Select(0)

    def move_command_to_bottom(self, event):
        selected_item = self.lista_de_comandos.GetFirstSelected()
        if selected_item >= 0 and selected_item < len(self.commands) - 1:
            self.commands.append(self.commands.pop(selected_item))
            self.lista_de_comandos.DeleteAllItems()
            for command in self.commands:
                self.add_command_to_list(command)
            self.lista_de_comandos.Select(len(self.commands) - 1)

class AddCommandDialog(wx.Dialog):
    def __init__(self, parent, id, title):
        super(AddCommandDialog, self).__init__(parent, id, title)

        panel = wx.Panel(self)

        # Add elements for entering name, description, command, and command type
        name_label = wx.StaticText(panel, -1, "Name:")
        self.name_text = wx.TextCtrl(panel, -1, "")

        desc_label = wx.StaticText(panel, -1, "Description:")
        self.desc_text = wx.TextCtrl(panel, -1, "")

        cmd_label = wx.StaticText(panel, -1, "Command:")
        self.cmd_text = wx.TextCtrl(panel, -1, "", style=wx.TE_MULTILINE)

        type_label = wx.StaticText(panel, -1, "Command type:")
        self.type_combo = wx.ComboBox(panel, -1, choices=["CMD", "Powershell"], style=wx.CB_READONLY)

        # "Ok" and "Cancel" buttons
        ok_button = wx.Button(panel, label="Ok")
        ok_button.Bind(wx.EVT_BUTTON, self.on_ok)

        cancel_button = wx.Button(panel, label="Cancel")
        cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)

        # Layout of the dialog box
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(name_label, 0, wx.ALL, 10)
        sizer.Add(self.name_text, 0, wx.EXPAND | wx.ALL, 10)
        sizer.Add(desc_label, 0, wx.ALL, 10)
        sizer.Add(self.desc_text, 0, wx.EXPAND | wx.ALL, 10)
        sizer.Add(cmd_label, 0, wx.ALL, 10)
        sizer.Add(self.cmd_text, 0, wx.EXPAND | wx.ALL, 10)
        sizer.Add(type_label, 0, wx.ALL, 10)
        sizer.Add(self.type_combo, 0, wx.EXPAND | wx.ALL, 10)
        sizer.Add(ok_button, 0, wx.CENTER | wx.ALL, 10)
        sizer.Add(cancel_button, 0, wx.CENTER | wx.ALL, 10)

        panel.SetSizer(sizer)

    def on_ok(self, event):
        self.EndModal(wx.ID_OK)

    def on_cancel(self, event):
        self.EndModal(wx.ID_CANCEL)

class OutputDialog(wx.Dialog):
    def __init__(self, parent, id, title, output):
        super(OutputDialog, self).__init__(parent, id, title, size=(400, 300))

        panel = wx.Panel(self)

        if output:
            output_text = wx.TextCtrl(panel, -1, value=output.strip(), style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL | wx.VSCROLL)
        else:
            output_text = wx.TextCtrl(panel, -1, value='The command was executed successfully!', style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL | wx.VSCROLL)

        close_button = wx.Button(panel, label="Close")
        close_button.Bind(wx.EVT_BUTTON, self.on_close)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(output_text, 1, wx.EXPAND | wx.ALL, 10)
        sizer.Add(close_button, 0, wx.CENTER | wx.ALL, 10)

        panel.SetSizer(sizer)

    def on_close(self, event):
        self.EndModal(wx.ID_OK)

def save_commands(commands):
    try:
        with open("commands", "wb") as file:
            pickle.dump(commands, file)
    except Exception as e:
        logging.error("Error saving commands: %s", e)

def load_commands():
    try:
        with open("commands", "rb") as file:
            return pickle.load(file)
    except FileNotFoundError:
        return []
    except Exception as e:
        logging.error("Error loading commands: %s", e)
        return []

def create_system_restore_point(description):
    try:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", "Checkpoint-Computer -Description '{}'".format(description), "", 1)
        wx.MessageBox("Restore point created successfully!", "Restore Point", wx.OK | wx.ICON_INFORMATION)
    except Exception as e:
        wx.MessageBox("Error creating restore point:\n" + str(e), "Restore Point Error", wx.OK | wx.ICON_ERROR)

def show_welcome_dialog():
    if not os.path.exists("welcome_indicator"):
        app = wx.App()
        dlg = WelcomeDialog(None, -1, "Welcome to Aurora")
        result = dlg.ShowModal()
        dlg.Destroy()
        app.MainLoop()

        open("welcome_indicator", "w").close()

def main():
    show_welcome_dialog()
    app = wx.App(False)
    frame = MyFrame(None, -1, "Aurora Windows Optimizer™")
    frame.Show()
    app.MainLoop()

if __name__ == "__main__":
    main()
