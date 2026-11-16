# Troubleshooting

[Home](../README.md) · [Getting started](getting-started.md) · [User guide](using-emergency-ai.md) · [Downloads](downloads.md)

Keep the app's terminal window open: it shows startup progress and error messages. When using a command below, open a terminal **inside your Emergency AI folder** first.

## Installation or downloads stopped

If the initial installer did not finish creating the app, reconnect to the internet and rerun `install.bat` or `sh install.sh`. The installer can reuse a verified Python download or resume a partial one. It refuses to overwrite an existing kit; if the app is already installed, use its launcher instead.

For failed model, library, or engine downloads after installation, resume the saved choices:

| Windows | Linux / macOS |
|---|---|
| `.\run.bat prepare --resume --os this` | `./run.sh prepare --resume --os this` |

This repairs components for the current computer. Omit `--os this` to prepare all platforms saved in the previous setup. If no choices were saved, run `.\run.bat prepare` or `./run.sh prepare` and choose again.

For the bootstrap installer, `install.log` normally lives in the sibling `.Emergency-AI-downloads` folder. At a drive or mounted-volume root, the cache is inside that root. See [installer details](technical-reference.md#installer-details).

## The window closed or the browser did not open

Run the launcher from a terminal so you can read its messages: `.\run.bat` on Windows or `./run.sh` on Linux/macOS. On Windows, you can open the folder in File Explorer, type `cmd` in its address bar, and press Enter to open Command Prompt there.

If the terminal says the server is running, open the printed address in your browser. The default is <http://127.0.0.1:8090>. Keep the terminal open while you use the app.

If a message says another service is using the port, choose another one with `.\run.bat start --port 8093` or `./run.sh start --port 8093`. Use the new address printed in the terminal.

## The app says search only

Search-only mode is expected when no AI model is available. Included guides still work.

If you wanted AI, check whether setup completed. Run `.\run.bat status` or `./run.sh status` to inspect the installed components. Wait if the terminal says the model is loading. If components are missing, resume setup while online.

If the engine exits while loading, check `logs/llm.log`. A model may need more memory than the computer can provide. Close other applications or choose a smaller installed model from the model menu. See [model choices](downloads.md#model-choices).

## Libraries are missing from the menu

Restart Emergency AI after downloading libraries. Check that the files are present in `zim/` and that setup installed the Kiwix server for this computer. Run the status command above for details. If you manage Kiwix separately, it must load the downloaded files too.

If libraries appear but are excluded from questions, check the **Libraries** dropdown and the **use Kiwix libraries** checkbox. Sidebar search searches the included guides, not the Kiwix libraries.

## My phone cannot connect

Keep the computer running Emergency AI and connect both devices to the same local network. Use the network address printed in the terminal or scan its QR code. Do not enter `127.0.0.1` on the phone: that address refers to the phone itself.

Check that you did not start the app with `--local-only`. Allow the app on the local network if the computer's firewall asks. Guest Wi-Fi or router device-isolation settings may prevent devices from communicating. VPNs or multiple network adapters can also change which address is shown.

Advanced users can select an interface with `start --host <LAN-IP>`. See [sharing instructions](using-emergency-ai.md#use-it-on-your-phone).

## There is not enough disk space

A library profile's size excludes the model and software. Installation also needs room to unpack downloads; an update may temporarily keep both old and new files.

Free space on the destination drive, then resume setup. Alternatively, rerun setup and select fewer downloads. Choosing `none` skips future downloads but does not delete existing model or library files. See [download choices](downloads.md).

## A response was interrupted or another answer is in progress

The app handles one answer at a time. Wait for the current answer or model switch to finish, then try again.

An interrupted response may omit steps or warnings. Read the linked source in full. The app does not automatically continue an incomplete answer. In the browser, a response whose stream ends without the completion event retains an interruption notice with its partial text in conversation history.

## The copied USB kit will not run

Make sure you copied the whole folder. Another operating system or processor may need different runtime files. Prepare the destination platform while online, include portable Python, and test the kit on that computer. See [moving the kit](using-emergency-ai.md#move-the-kit-to-a-usb-drive-or-another-computer).

## Still stuck

Report the operating system, the command or launcher you used, the exact error, and whether the problem happened during installation or normal use in a [GitHub issue](https://github.com/skanga/Emergency-AI/issues). Review any logs before sharing them; include only the relevant error details.
