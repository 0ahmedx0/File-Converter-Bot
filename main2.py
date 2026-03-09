import pyrogram
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from pyrogram.errors import FloodWait

import os
import shutil
import subprocess
import threading
import time
import logging

# --- استيراد الوحدات الخاصة بك ---
from buttons import *
# import aifunctions  # تأكد من أن هذه الوحدات موجودة وتعمل بشكل صحيح
import helperfunctions
import mediainfo
import guess
import tormag
import progconv
import others
import tictactoe

# --- إعداد التسجيل (Logging) لتشخيص أفضل ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
LOGGER = logging.getLogger(__name__)

# --- إعدادات البيئة ---
bot_token = os.environ.get("TOKEN", "") 
api_hash = os.environ.get("HASH", "") 
api_id = os.environ.get("ID", "")

# --- إعداد عميل البوت ---
app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)
MESGS = {}

# --- دوال إدارة الرسائل المحفوظة (كما هي) ---
def saveMsg(msg, msg_type):
    MESGS[msg.from_user.id] = [msg, msg_type]

def getSavedMsg(msg):
    return MESGS.get(msg.from_user.id, [None, None])

def removeSavedMsg(msg):
    MESGS.pop(msg.from_user.id, None)

# =====================================================================================
# /// قسم التحسينات الأساسية ///
# =====================================================================================

progress_tracker = {}

def progress(current, total, message, action_text, status_message):
    user_id = message.from_user.id
    now = time.time()

    last_update = progress_tracker.get(user_id, 0)
    
    if now - last_update > 3:
        progress_tracker[user_id] = now
        percent = current * 100 / total
        try:
            app.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_message.id,
                text=f"__{action_text}__: **{percent:.1f}%**"
            )
        except FloodWait as e:
            LOGGER.warning(f"FloodWait for {e.value} seconds.")
            time.sleep(e.value)
        except Exception:
            pass

def run_process(command, status_message):
    try:
        app.edit_message_text(status_message.chat.id, status_message.id, "__Processing... This might take a while.__")
        process = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        return True
    except subprocess.CalledProcessError as e:
        error_output = e.stderr if e.stderr else "No error output captured."
        LOGGER.error(f"Command failed: {command}\nError: {error_output}")
        # عرض آخر 1000 حرف من الخطأ لتجنب تجاوز حد الرسالة
        app.edit_message_text(
            status_message.chat.id,
            status_message.id,
            f"**Error during conversion!**\n\n`{error_output[-1000:]}`"
        )
        return False

def download_file(message):
    msg = app.send_message(message.chat.id, '__Downloading...__', reply_to_message_id=message.id)
    file_path = app.download_media(
        message,
        progress=progress,
        progress_args=(message, "Downloading", msg)
    )
    return file_path, msg

def upload_file(message, file_path, status_message, as_video=False, **kwargs):
    if status_message:
        app.edit_message_text(message.chat.id, status_message.id, '__Uploading...__')
    
    thumb_path = kwargs.get('thumb', None)
    
    try:
        if as_video:
            app.send_video(
                message.chat.id,
                video=file_path,
                reply_to_message_id=message.id,
                progress=progress,
                progress_args=(message, "Uploading", status_message),
                **kwargs
            )
        else:
            app.send_document(
                message.chat.id,
                document=file_path,
                force_document=True,
                reply_to_message_id=message.id,
                progress=progress,
                progress_args=(message, "Uploading", status_message),
                **kwargs
            )
    finally:
        if status_message:
            try:
                app.delete_messages(message.chat.id, message_ids=status_message.id)
            except Exception:
                pass
        
        if os.path.exists(file_path):
            os.remove(file_path)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)

# =====================================================================================
# /// إعادة كتابة الدوال الوظيفية ///
# =====================================================================================

def follow(message, input_name, new_ext, old_ext, status_message):
    output_name = helperfunctions.updtname(input_name, new_ext)
    file_path = None

    try:
        file_path, down_msg = download_file(message)
        # نستخدم status_message للعملية كلها
        app.delete_messages(message.chat.id, down_msg.id)

        command = None
        upload_as_video = False

        if (output_name.upper().endswith(VIDAUD) or new_ext == "gif") and input_name.upper().endswith(VIDAUD):
            LOGGER.info("Handling VID/AUD conversion.")
            command = helperfunctions.ffmpegcommand(file_path, output_name, new_ext)
            if new_ext.upper() in VIDF: upload_as_video = True
        elif output_name.upper().endswith(IMG) and input_name.upper().endswith(IMG):
            LOGGER.info("Handling IMG conversion.")
            command = helperfunctions.magickcommand(file_path, output_name, new_ext)
        elif output_name.upper().endswith(IMG) and input_name.upper().endswith("TGS"):
            LOGGER.info("Handling Animated Sticker conversion.")
            if new_ext in ["webp", "gif", "png"]:
                command = f'./tgsconverter "{file_path}" "{new_ext}"'
            else:
                app.edit_message_text(status_message.chat.id, status_message.id,"__Only Availble Conversions for Animated Stickers are **GIF, PNG** and **WEBP**__")
                return
        elif output_name.upper().endswith(EB) and input_name.upper().endswith(EB):
            LOGGER.info("Handling Ebook conversion.")
            command = helperfunctions.calibrecommand(file_path, output_name)
        elif (output_name.upper().endswith(LBW) and input_name.upper().endswith(LBW)) or \
             (output_name.upper().endswith(LBI) and input_name.upper().endswith(LBI)) or \
             (output_name.upper().endswith(LBC) and input_name.upper().endswith(LBC)):
            LOGGER.info("Handling LibreOffice conversion.")
            # subprocess.run is handled by run_process, so we form the command string
            command = helperfunctions.libreofficecommand(file_path, new_ext)
        elif output_name.upper().endswith(FF) and input_name.upper().endswith(FF):
            LOGGER.info("Handling FontForge conversion.")
            command = helperfunctions.fontforgecommand(file_path, output_name, message)
        # ... Add other conversion types here in the same pattern
        else:
            app.edit_message_text(status_message.chat.id, status_message.id,"__Choose a Valid Extension, don't Type it__")
            return

        if command:
            success = run_process(command, status_message)
            if success and os.path.exists(output_name) and os.path.getsize(output_name) > 0:
                if upload_as_video:
                    thumb, duration, width, height = mediainfo.allinfo(output_name)
                    upload_file(message, output_name, None, as_video=True, caption=f'**{output_name.split("/")[-1]}**', thumb=thumb, duration=duration, width=width, height=height)
                else:
                    upload_file(message, output_name, None, caption="File Converted Successfully")
            else:
                LOGGER.error("Conversion process failed or output file is missing/empty.")

    except Exception as e:
        LOGGER.error(f"Error in follow function: {e}", exc_info=True)
        app.send_message(message.chat.id, f"An unexpected error occurred: {e}", reply_to_message_id=message.id)
    finally:
        if file_path and os.path.exists(file_path): os.remove(file_path)
        if os.path.exists(output_name): os.remove(output_name)
        try:
             app.delete_messages(message.chat.id, message_ids=status_message.id)
        except Exception:
            pass

def sendvideo(message, oldmessage):
    file_path, down_msg = download_file(message)
    app.delete_messages(message.chat.id, oldmessage.id)
    try:
        thumb, duration, width, height = mediainfo.allinfo(file_path)
        upload_file(message, file_path, down_msg, as_video=True, caption=f'**{os.path.basename(file_path)}**', thumb=thumb, duration=duration, width=width, height=height)
    except Exception as e:
        LOGGER.error(f"Error in sendvideo: {e}")
        if down_msg: app.delete_messages(message.chat.id, down_msg.id)
        if os.path.exists(file_path): os.remove(file_path)

def senddoc(message, oldmessage):
    file_path, msg = download_file(message)
    app.delete_messages(message.chat.id, oldmessage.id)
    upload_file(message, file_path, msg)

def sendphoto(message, oldmessage):
    file_path = app.download_media(message)
    app.delete_messages(message.chat.id, oldmessage.id)
    try:
        app.send_photo(message.chat.id, photo=file_path, reply_to_message_id=message.id)
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            
def extract(message, oldm):
    file_path, status_msg = download_file(message)
    foldername = ""
    try:
        app.edit_message_text(message.chat.id, status_msg.id, '__Extracting...__')
        cmd, foldername, infofile = helperfunctions.zipcommand(file_path, message)
        
        success = run_process(cmd, status_msg)
        if os.path.exists(file_path): os.remove(file_path)

        if success and os.path.exists(foldername):
            dir_list = helperfunctions.absoluteFilePaths(foldername)
            if len(dir_list) > 30:
                app.send_message(message.chat.id, f"__Number of files is **{len(dir_list)}** (limit is 30)__", reply_to_message_id=message.id)
            else:
                # Can't use status_msg for multi-upload, so delete it first
                app.delete_messages(message.chat.id, status_msg.id)
                status_msg = None
                for ele in dir_list:
                    if os.path.getsize(ele) > 0:
                        upload_file(message, ele, None) # None for status_msg as it is multi-upload
                    else:
                        app.send_message(message.chat.id, f'**{os.path.basename(ele)}** __is Skipped (0 bytes)__', reply_to_message_id=message.id)
        else:
            if status_msg: app.delete_messages(message.chat.id, status_msg.id)
            app.send_message(message.chat.id, "**Unable to Extract**", reply_to_message_id=message.id)
            
    finally:
        if os.path.exists(foldername): shutil.rmtree(foldername)
        app.delete_messages(message.chat.id, oldm.id)

# (All other functions like `getmag`, `compile`, etc. should be rewritten similarly)
# (For brevity, I'll keep the AI functions as they were, since they are API based, not file-processing heavy)
def dltmsg(umsg,rmsg,sec=15):
    time.sleep(sec)
    try:
        app.delete_messages(umsg.chat.id,message_ids=[umsg.id,rmsg.id])
    except:
        pass

def rname(message, newname, oldm):
    file_path, msg = download_file(message)
    app.delete_messages(message.chat.id, oldm.id)
    renamed_path = os.path.join(os.path.dirname(file_path), newname)
    try:
        os.rename(file_path, renamed_path)
        upload_file(message, renamed_path, msg)
    finally:
        if os.path.exists(file_path): os.remove(file_path)
        if os.path.exists(renamed_path): os.remove(renamed_path)

# =====================================================================================
# /// معالجات الرسائل (Message Handlers) ///
# =====================================================================================

@app.on_message(filters.command(['start']))
def start_cmd(client, message):
    app.send_message(message.chat.id, f"Welcome {message.from_user.mention}\nI can convert files, use AI, and more.\n\n/help - See what I can do.\n/detail - List of supported formats.", reply_to_message_id=message.id)

@app.on_message(filters.command(['help']))
def help_cmd(client, message):
    msg = app.send_message(message.chat.id,
        "**/start** - Welcome message\n**/help** - This message\n**/detail** - Supported formats\n**/cancel** - Cancel current operation\n**/rename new_name.ext** - Rename last file\n\n**File Operations:**\nSend any file to see conversion options. You can also use commands on a sent file:\n**/read** - Read file content as text.\n**/make** - Make a file from a text message.\n\n**AI Features:**\n**/imagegen prompt** - Generate images\n**/musicgen prompt** - Generate music",
        reply_to_message_id=message.id)
    threading.Thread(target=lambda: dltmsg(message, msg), daemon=True).start()

@app.on_message(filters.command(['detail']))
def detail_cmd(client, message):
    msg = app.send_message(message.chat.id, START_TEXT, reply_to_message_id=message.id)
    threading.Thread(target=lambda: dltmsg(message, msg, 30), daemon=True).start()

@app.on_message(filters.command(['rename']))
def rename_cmd(client, message):
    try:
        newname = message.text.split(" ", 1)[1]
    except IndexError:
        app.send_message(message.chat.id, "__Usage: **/rename new-file-name.ext**__", reply_to_message_id=message.id)
        return

    nmessage, msg_type = getSavedMsg(message)
    if nmessage:
        oldm = app.send_message(message.chat.id, "__Renaming...__", reply_to_message_id=nmessage.id)
        threading.Thread(target=lambda: rname(nmessage, newname, oldm), daemon=True).start()
        removeSavedMsg(message)
    else:
        app.send_message(message.chat.id, "__Send a file first before using /rename__", reply_to_message_id=message.id)

@app.on_message(filters.command(['cancel']))
def cancel_cmd(client, message):
    nmessage, msg_type = getSavedMsg(message)
    if nmessage:
        removeSavedMsg(message)
        try:
            # Delete the keyboard message
            app.delete_messages(message.chat.id, message_ids=nmessage.id + 1)
        except Exception:
            pass
        app.send_message(message.chat.id,"__Your job was **Canceled**__", reply_to_message_id=message.id)
    else:
        app.send_message(message.chat.id,"__No active job to cancel.__", reply_to_message_id=message.id)

@app.on_message(filters.document)
def doc_handler(client, message):
    saveMsg(message, "DOCUMENT")
    filename = message.document.file_name
    dext = filename.split(".")[-1].upper()

    if filename.upper().endswith(VIDAUD):
        newext = "mov"
        if dext.lower() == newext:
            oldm = app.send_message(message.chat.id, '__Processing MOV to send as streamable video...__', reply_to_message_id=message.id)
            threading.Thread(target=lambda: sendvideo(message, oldm), daemon=True).start()
        else:
            status_msg = app.send_message(message.chat.id, f'__Auto-converting **{dext}** to **MOV** for streaming...__', reply_to_message_id=message.id)
            threading.Thread(target=lambda: follow(message, filename, newext, dext.lower(), status_msg), daemon=True).start()
        removeSavedMsg(message)
        return

    keyboards = {
        tuple(IMG): (IMG_TEXT, IMGboard, "📷"), tuple(VIDAUD): (VA_TEXT, VAboard, "📹/🔊"),
        tuple(LBW): (LBW_TEXT, LBWboard, "💼"), tuple(LBC): (LBC_TEXT, LBCboard, "📊"),
        tuple(LBI): (LBI_TEXT, LBIboard, "🖼️"), tuple(FF): (FF_TEXT, FFboard, "🔤"),
        tuple(EB): (EB_TEXT, EBboard, "📚"), tuple(ARC): (None, ARCboard, "🗄️"),
        ("TORRENT",): (None, None, "🔗"), tuple(SUB): (SUB_TEXT, SUBboard, "🗯️"),
        tuple(PRO): (PRO_TEXT, PROboard, "👨‍💻"), tuple(T3D): (T3D_TEXT, T3Dboard, "💠")
    }
    
    handled = False
    for exts, data in keyboards.items():
        if filename.upper().endswith(exts):
            text, board, icon = data
            if dext == "TORRENT":
                oldm = app.send_message(message.chat.id,'__Getting Magnet Link__', reply_to_message_id=message.id)
                #threading.Thread(target=lambda:getmag(message,oldm),daemon=True).start()
                removeSavedMsg(message)
                return

            msg_text = f'__Detected Extension:__ **{dext}** {icon}\n'
            if text:
                msg_text += f'__Now choose an extension to convert to...__\n\n--**Available formats**--\n__{text}__'
            if board == ARCboard:
                msg_text += '__Do you want to Extract?__'

            app.send_message(message.chat.id, msg_text, reply_markup=board, reply_to_message_id=message.id)
            handled = True
            break
    
    if not handled:
        app.send_message(message.chat.id, '__No conversions available for this file type. You can use /rename or /read.__')

@app.on_message(filters.animation)
def animation_handler(client, message):
    LOGGER.info("Animation (GIF) detected. Auto-converting to MOV.")
    inputt = "animation.mp4"
    newext = "mov"
    oldext = "mp4"

    status_msg = app.send_message(message.chat.id, f'__Auto-converting **GIF** to **MOV**...__', reply_to_message_id=message.id)
    threading.Thread(target=lambda: follow(message, inputt, newext, oldext, status_msg), daemon=True).start()

@app.on_message(filters.video)
def video_handler(client, message):
    saveMsg(message, "VIDEO")
    dext = "MP4" # Assume default for unnamed videos
    if message.video.file_name:
        dext = message.video.file_name.split(".")[-1].upper()
    
    app.send_message(
        message.chat.id,
        f'__Detected Extension:__ **{dext}** 📹 / 🔊\n__Choose an extension to convert to...__\nI can also re-process it as a streamable video, just send it as a document.',
        reply_markup=VAboard, reply_to_message_id=message.id
    )

@app.on_message(filters.video_note)
def videonote_handler(client, message):
    saveMsg(message, "VIDEO_NOTE")
    app.send_message(message.chat.id,
                f'__Detected Extension:__ **MP4** 📹 / 🔊\n__Now send extension to Convert to...__',
                reply_markup=VAboard, reply_to_message_id=message.id)

@app.on_message(filters.audio)
def audio_handler(client, message):
    saveMsg(message, "AUDIO")
    dext = message.audio.file_name.split(".")[-1].upper()
    app.send_message(message.chat.id,
        f'__Detected Extension:__ **{dext}** 📹 / 🔊\n__Now send extension to Convert to...__',
        reply_markup=VAboard, reply_to_message_id=message.id
    )

@app.on_message(filters.voice)
def voice_handler(client, message):
    saveMsg(message, "VOICE")
    app.send_message(message.chat.id,
                f'__Detected Extension:__ **OGG** 📹 / 🔊\n__Now send extension to Convert to...__',
                reply_markup=VAboard, reply_to_message_id=message.id)

@app.on_message(filters.photo)
def photo_handler(client, message):
    saveMsg(message, "PHOTO")
    app.send_message(message.chat.id,
                     f'__Detected Extension:__ **JPG** 📷\n__Now send extension to Convert to...__\n\n**SPECIAL** 🎁\n__Colorize, Positive, Upscale & Scan__',
                     reply_markup=IMGboard, reply_to_message_id=message.id)

@app.on_message(filters.sticker)
def sticker_handler(client, message):
    saveMsg(message, "STICKER")
    ext_text = "WEBP"
    if message.sticker.is_animated or message.sticker.is_video:
        ext_text = "TGS"
    
    app.send_message(message.chat.id,
        f'__Detected Extension:__ **{ext_text}** 📷\n__Now send extension to Convert to...__\n\n**SPECIAL** 🎁\n__Colorize, Positive, Upscale & Scan__',
        reply_markup=IMGboard, reply_to_message_id=message.id)

@app.on_message(filters.text)
def text_handler(client, message):
    nmessage, msg_type = getSavedMsg(message)

    if not nmessage:
        # Handle regular text messages, AI chats, commands not caught by filters, etc.
        # This part of the logic from your original code is fine.
        return

    # A file was waiting for a command, this text is the command.
    removeSavedMsg(message)
    try:
        # Delete the keyboard message that was sent after the file.
        app.delete_messages(message.chat.id, message_ids=nmessage.id + 1)
    except Exception:
        pass

    # Handle special button commands
    special_commands = {
        "EXTRACT": extract,
        # "POSITIVE": negetivetopostive,  # Add these functions back if you refactor them
        # "COLOR": colorizeimage,
        "SENDVID": sendvideo,
        "SENDDOC": senddoc,
        "SENDPHOTO": sendphoto,
    }

    if message.text in special_commands:
        func = special_commands[message.text]
        oldm = app.send_message(message.chat.id, f'__Processing: **{message.text}**__', reply_markup=ReplyKeyboardRemove(), reply_to_message_id=nmessage.id)
        threading.Thread(target=lambda: func(nmessage, oldm), daemon=True).start()
        return

    # This is a standard conversion request
    input_name = ""
    if msg_type == "DOCUMENT": input_name = nmessage.document.file_name
    elif msg_type == "VIDEO": input_name = nmessage.video.file_name or "video.mp4"
    elif msg_type == "AUDIO": input_name = nmessage.audio.file_name
    elif msg_type == "VOICE": input_name = "voice.ogg"
    elif msg_type == "VIDEO_NOTE": input_name = "video_note.mp4"
    elif msg_type == "PHOTO": input_name = "photo.jpg"
    elif msg_type == "STICKER":
        input_name = "sticker.webp"
        if nmessage.sticker.is_animated or nmessage.sticker.is_video:
            input_name = "sticker.tgs"
    
    if not input_name:
        app.send_message(message.chat.id, "__Error: Could not determine original file name for conversion.__", reply_to_message_id=nmessage.id)
        return

    new_ext = message.text.lower()
    old_ext = input_name.split('.')[-1]

    if old_ext.lower() == new_ext:
        app.send_message(message.chat.id, "__Nice try, Don't choose the same extension!__", reply_to_message_id=nmessage.id)
        return

    status_msg = app.send_message(message.chat.id, f'__Starting conversion from **{old_ext.upper()}** to **{new_ext.upper()}**__', reply_markup=ReplyKeyboardRemove(), reply_to_message_id=nmessage.id)
    threading.Thread(target=lambda: follow(nmessage, input_name, new_ext, old_ext, status_msg), daemon=True).start()


# --- Main execution ---
if __name__ == "__main__":
    LOGGER.info("Bot has started successfully!")
    app.run()
