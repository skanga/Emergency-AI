# Using Emergency AI

[Home](../README.md) · [Getting started](getting-started.md) · [Using the app](using-emergency-ai.md) · [Downloads](downloads.md) · [Help](troubleshooting.md) · [Reference](technical-reference.md)

## Open and close the app

Open the same launcher each time, from the folder where you installed Emergency AI.

| Computer | Open |
|---|---|
| Windows | Double-click `run.bat`. |
| macOS | Double-click `run.command`. On first use, right-click it and choose **Open** if needed. |
| Linux | Open a terminal in the folder and run `./run.sh`. |

Keep the terminal window open while using the app. Closing the browser does not stop the app. To stop it, return to its terminal window and press **Ctrl+C**.

## Read a guide or ask a question

1. Choose a guide in the sidebar, or use **Search the guides…** to find a topic.
2. To ask a question, choose **Ask the AI**, type your question, and send it.
3. Open the source links under the response to read the original material.

Without a running AI model, questions return source passages. This is normal search-only operation. If a source is too long to include in an answer, follow its link to read it in full. Source previews are shorter than the original instructions.

An incomplete or interrupted response is unfinished. Read the original source before relying on the answer. The app does not automatically continue an unfinished answer.

Use the **Print** button while reading a guide to keep a paper copy.

## Change language

Use the EN/PT/ES buttons. English is the default. You can also start in Portuguese or Spanish with `--lang pt` or `--lang es`.

## Use it on your phone

Keep Emergency AI running on the computer. Connect the phone to the same local network, then scan the QR code shown in the computer's terminal. You can also enter the printed network address in the phone's browser.

The computer runs the app; the phone displays it. The computer and local network must stay powered, but the network does not need an internet connection after setup.

Sharing is enabled by default. Connected devices can read all indexed documents, including your personal documents. To use only this computer, start with `.\run.bat --local-only` on Windows or `./run.sh --local-only` on Linux/macOS.

If no QR code appears, use the printed network address. Multiple network adapters or VPNs can affect the detected address; see [phone troubleshooting](troubleshooting.md#my-phone-cannot-connect).

## Choose models and libraries

To change AI models, click the current model indicator in the top bar and choose an installed model from its menu. The same control is available on phones. A switch waits for any current answer to finish, unloads the previous model, then shows loading progress and elapsed time. Guide browsing and search remain available. The choice applies to all browsers connected to this server and is saved in `config/settings.local.json` after the new model loads successfully. Only one app-managed model stays loaded at a time. Switching controls are disabled for externally managed AI servers (such as Ollama or LM Studio) and when using `--no-engines`.

The **Libraries** dropdown beside the model selector filters Kiwix sources for your questions. All available libraries are selected by default; check individual libraries to narrow the search. Selecting none searches only the included guides. The selection is remembered in this browser and does not affect other browsers, restart Kiwix, or change the installed libraries. The **use Kiwix libraries** checkbox below the question remains the overall on/off control. The sidebar search continues to search the included guides.

## Add your own documents

1. Save your document as a Markdown (`.md`) or plain text (`.txt`) file.
2. Put it in the `knowledge/extra/` folder inside Emergency AI.
3. Restart the app so the document is included in searches.

These documents are searched in all three languages. PDFs, images, and other file types are not indexed directly. Files named `README.md` are skipped. Personal documents are also available to other devices connected to the app.

## Move the kit to a USB drive or another computer

Copy the **entire Emergency AI folder**, including downloaded models, libraries, and software. Use an **exFAT** drive if you need compatibility across Windows, macOS, and Linux: some downloaded files are larger than FAT32's 4 GB file limit. Formatting a drive erases its contents, so back up anything you need first.

Preparing the kit for one computer does not install the software for every operating system and processor. Before travelling, run setup while online and choose **Windows + Linux + macOS** if you need the supported platforms. Include portable Python when prompted. See [downloads](downloads.md#advanced-preparation) for explicit platform options.

Test the copied kit on the destination computer while you can still fix missing components. Then use the [offline check](getting-started.md#check-that-it-works-offline).
