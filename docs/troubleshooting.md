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

Setup downloads require HTTPS, including redirects. Python and llama.cpp downloads (including CUDA companion libraries) also require a valid GitHub SHA-256 digest. If setup reports a missing or invalid digest, it stops that component before downloading; it does not replace the existing installation. Retry when the publisher provides valid metadata. A checksum mismatch rejects the new download and retains the installed version.

Preparation and component upgrades reject archive paths that escape the destination, existing destination symlinks, and special files. These checks also apply on older supported Python versions. Safe internal TAR links are preserved during preparation or materialized when required by the platform or upgrade procedure. ZIP symlink entries are rejected. If an archive is rejected, retain the error message and retry with a corrected publisher archive.

For the bootstrap installer, `install.log` normally lives in the sibling `.Emergency-AI-downloads` folder. At a drive or mounted-volume root, the cache is inside that root. See [installer details](technical-reference.md#installer-details).

## The window closed or the browser did not open

Run the launcher from a terminal so you can read its messages: `.\run.bat` on Windows or `./run.sh` on Linux/macOS. On Windows, you can open the folder in File Explorer, type `cmd` in its address bar, and press Enter to open Command Prompt there.

If the terminal says the server is running, open the printed address in your browser. The default is <http://127.0.0.1:8090>. Keep the terminal open while you use the app.

If a message says another service is using the port, choose another one with `.\run.bat start --port 8093` or `./run.sh start --port 8093`. Use the new address printed in the terminal.

## The app says search only

Search-only mode is expected when no AI model is available. Included guides still work.

If you wanted AI, check whether setup completed. Run `.\run.bat status` or `./run.sh status` to inspect the installed components. Wait if the terminal says the model is loading. If components are missing, resume setup while online.

If the engine exits while loading, check `logs/llm.log`. A model may need more memory than the computer can provide. Close other applications or choose a smaller installed model from the model menu. See [model choices](downloads.md#model-choices).

## The AI uses CPU even though a GPU is installed

The launcher tests each installed GPU engine before loading the model. It reports whether the probe crashed, timed out, or found no usable devices, then tries the next backend. Check `logs/gpu-probe.log` for the executable, exit code, and driver error output. Model-loading errors are in `logs/llm.log`. `AI ready using cuda` confirms CUDA model startup succeeded.

On WSL, the launcher automatically prefers the Windows-provided NVIDIA driver libraries for CUDA. This avoids mixing the WSL driver with an Ubuntu-installed PTX compiler. It discovers the directory each time the kit starts; no machine-specific shell variable is normally needed. If several driver directories exist and none can be matched to the active driver, it preserves the existing library path rather than guessing. The probe log records when no WSL directory was selected. The launcher does not install or remove drivers.

## Libraries are missing from the menu

Restart Emergency AI after downloading libraries. Check that the files are present in `zim/` and that setup installed the Kiwix server for this computer. Run the status command above for details. If you manage Kiwix separately, it must load the downloaded files too.

Wait for `Kiwix ready` in the terminal. The launcher checks the catalog before reporting success and stops a server that fails to become ready within 30 seconds. Check `logs/kiwix.log` if startup fails. A port occupied by a different service is reported as a conflict.

Some WSL systems have multiple IPv4 addresses on the loopback interface. Kiwix can then reject `127.0.0.1` as unavailable even though it exists. For that exact startup error, the launcher retries once with `--address ipv4` and prints a notice. This fallback listens on all IPv4 interfaces, so the Kiwix libraries may be reachable directly from your network. Other startup failures do not trigger this fallback. A separate Kiwix terminal is no longer needed for this case.

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

## Libraries are enabled but no library passage was used

Open **Source search and coverage** beneath the answer. A successful search can still lead to a fetch failure, irrelevant passages or passages that cannot fit. **Not used in this answer** lists omitted references and reasons. A library being reachable does not mean its search or PDF index is working.

- **Archive unavailable / catalog unavailable:** verify the local Kiwix server and selected archive. Saved logical names survive archive version updates; a removed library is reported explicitly.
- **No matches:** native search succeeded without results. **No relevant passage** means matches were found but rejected as evidence.
- **Article fetch failures:** search worked, but article content could not be read within the body/time limits.
- **PDF index needed:** prepare the selected document collection explicitly. Merely installing a ZIM does not index its PDFs.
- **Partially indexed / browse only:** inspect the preparation report for excluded pages or failed documents. Scans and suspect layouts are not supplied as reliable text; no automatic OCR runs during an answer.
- **Unresolved disagreement:** the application withholds the contested recommendation. A reviewed, version-specific policy can resolve a known conflict without changing the original guide.

```sh
python3 emergency.py diagnose-retrieval --libraries wikipedia_en_medicine 'My child is choking.'
python3 emergency.py index-libraries --libraries zimgit-medicine_en --prepare-tool
```

The second command may download the pinned extraction tool; ordinary questions never do. If an index refresh fails or is cancelled, the previous valid index for that archive version remains active. A new archive UUID requires preparation of the new version. To explicitly remove indexes for unselected or superseded archives, add `--cleanup` to `index-libraries`; this does not remove source documents or ZIMs.
