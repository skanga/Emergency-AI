# Getting started

[Home](../README.md) · [User guide](using-emergency-ai.md) · [Downloads](downloads.md) · [Help](troubleshooting.md)

Install while you have internet. You need a powered computer to use the app later. The included guides work without an AI model; AI and extra libraries are optional downloads.

## Download and run the installer

Create a new, empty folder named **Emergency-AI** somewhere easy to find, such as your Desktop. Keep the whole installation together in this folder.

### Windows

1. Right-click [Download install.bat](https://raw.githubusercontent.com/skanga/Emergency-AI/main/install.bat) and choose **Save link as**.
2. Save it in your Emergency-AI folder. Keep the filename `install.bat`; do not add `.txt`.
3. Open the folder in File Explorer and double-click `install.bat`.
4. Keep the installer window open. Wait for the message showing where Emergency AI was installed.

The [Windows walkthrough](https://github.com/user-attachments/assets/3c3d246f-f09e-45c0-a4ba-8772f8008c8d) shows installation and first use.

### macOS

1. Right-click [Download install.sh](https://raw.githubusercontent.com/skanga/Emergency-AI/main/install.sh) and save it in your Emergency-AI folder.
2. Open the **Terminal** app.
3. Type `cd `, including the space, then drag your Emergency-AI folder from Finder into Terminal. Press **Return**.
4. Enter `sh install.sh` and press **Return**.
5. Keep Terminal open while installation runs.

### Linux

1. Right-click [Download install.sh](https://raw.githubusercontent.com/skanga/Emergency-AI/main/install.sh) and save it in your Emergency-AI folder.
2. Open the folder in your file manager. Use **Open in Terminal** if your file manager provides it. Otherwise open a terminal and use `cd` to enter that folder.
3. Run `sh install.sh`.
4. Keep the terminal open while installation runs.

The installer supplies Python. You do not need Git or a separate Python installation. See [supported platforms and required system tools](technical-reference.md#terminal-installation-and-platform-support) if installation reports a missing tool.

## Choose your downloads

The installer asks **Run first-time setup now…? [Y/n]**. Enter `y` to choose downloads, or `n` to skip them for now.

For the smallest setup, skip downloads and [open the app](#open-the-app). At its first-use menu, choose **Use guides now and remember this choice**. This opens the included guides without an AI model.

For a small setup with AI and extra references, use these selections:

| Prompt | Suggested selection | Why |
|---|---|---|
| Setup options | **Recommended choices** | Keeps advanced models and archived libraries out of the menu. |
| AI model | **LFM3 1.7B** (`lfm3-1.7b`) | Smallest recommended model download, about 1.1 GB. Recommended system RAM: 8 GB. |
| Kiwix libraries | **minimal** | About 3 GiB of extra reference material. |
| Systems | **This computer only** | Downloads software for the computer you are using. |
| Portable Python, if asked | Yes if you need the missing runtimes | This computer's installer normally already supplies it. |
| NVIDIA CUDA, if offered | No for a smaller download | Optional acceleration; AI also works without this download. |
| Confirmation | Yes, after checking the selections | Starts the downloads. |

Enter the number shown beside the choice. Do not assume every default matches this table: interactive library setup defaults to **recommended**, which is a larger download than **minimal**.

Choose **None** for the model if you only want to read and search documents. You can also choose **None** for libraries. The included guides remain available in both cases.

Model RAM figures are recommendations, not guaranteed minimums. Larger models and library collections need more memory or storage. See [Downloads and models](downloads.md) before choosing them. Setup also asks for library languages (EN/PT/ES or all) and optionally English reference collections. Profile estimates include all languages; confirmation shows the filtered size. The minimal profile is English-only.

Wait for setup to finish. Download times depend on your connection and selections. If setup reports a failure, follow [download recovery](troubleshooting.md#installation-or-downloads-stopped).

## Open the app

After successful setup, the installer may offer to open the app. You can also open it from your Emergency AI folder:

| Computer | Launcher |
|---|---|
| Windows | Double-click `run.bat`. |
| macOS | Double-click `run.command`; if needed on first use, right-click and choose **Open**. |
| Linux | Run `./run.sh` in a terminal in the folder. |

Keep the terminal window open. The browser should open at <http://127.0.0.1:8090>. If it does not, copy the address printed in the terminal into your browser.

Open a guide from the sidebar, then try **Search the guides…**. Use **Ask the AI** to ask a question; without a running model, the response contains source passages instead. Open a source link to check the original material.

To stop the app, return to its terminal and press **Ctrl+C**. Next time, use the same launcher rather than running the installer again.

## Check that it works offline

Do this while you still have time to repair missing downloads:

1. Stop Emergency AI with **Ctrl+C**.
2. Disconnect the computer from internet access.
3. Open Emergency AI with its launcher.
4. Open an included guide and run a search.
5. If you downloaded AI, ask a question and check that the model is available. Allow time for it to load.
6. If you downloaded libraries, open one of their source links and confirm that the article loads.

For phone testing, keep both devices connected to a powered local network while disconnecting that network's internet connection. See [phone access](using-emergency-ai.md#use-it-on-your-phone).

The online videos and external reference websites will not work without internet. Saved guides and downloaded library articles should work. If something is missing, reconnect and use [Troubleshooting](troubleshooting.md).
