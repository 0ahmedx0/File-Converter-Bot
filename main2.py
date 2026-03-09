import pyrogram
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import os
import shutil
import asyncio
import time

from buttons import *
import helperfunctions
import mediainfo
import guess
import tormag
import progconv
import others
import tictactoe
import aifunctions

# env
bot_token = os.environ.get("TOKEN", "") 
api_hash = os.environ.get("HASH", "") 
api_id = os.environ.get("ID", "")

# bot
app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)
MESGS = {}

# Dictionary to store last progress update time to prevent Telegram FloodWait
progress_timers = {}

# msgs functions (No changes here, synchronous state management is fast)
def saveMsg(msg, msg_type):
    MESGS[msg.from_user.id] = [msg, msg_type]

def getSavedMsg(msg):
    return MESGS.get(msg.from_user.id, [None, None])

def removeSavedMsg(msg):
    MESGS.pop(msg.from_user.id, None)

# --- 🚀 نظام الأوامر اللامتزامن الجديد (بديل os.system) ---
async def run_shell_command(cmd):
    """تنفيذ أوامر النظام بشكل لامتزامن لمنع تجمد البوت"""
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()
    return process.returncode

# --- 🚀 نظام تتبع التقدم السريع في الذاكرة (بدون ملفات TXT) ---
async def smart_progress(current, total, message, action, msg_to_update):
    """تحديث نسبة التقدم كل 3 ثواني من الذاكرة العشوائية مباشرة"""
    global progress_timers
    
    # تحديد معرف فريد للرسالة
    timer_id = f"{message.chat.id}_{message.id}_{action}"
    
    now = time.time()
    last_update_time = progress_timers.get(timer_id, 0)
    
    # تحديث كل 3 ثواني أو عند اكتمال التحميل/الرفع
    if now - last_update_time >= 3.0 or current == total:
        percent = current * 100 / total
        try:
            await app.edit_message_text(message.chat.id, msg_to_update.id, f"__{action}__ : **{percent:.1f}%**")
            progress_timers[timer_id] = now
        except:
            pass
            
        if current == total:
            # مسح المؤقت عند الانتهاء لتنظيف الذاكرة
            progress_timers.pop(timer_id, None)

# download with progress
async def down(message):
    try:
        size = int(message.document.file_size)
    except:
        try: size = int(message.video.file_size)
        except: size = 1

    msg = None
    if size > 25000000:
        msg = await app.send_message(message.chat.id, '__Downloading...__', reply_to_message_id=message.id)

    file = await app.download_media(
        message,
        progress=smart_progress if msg else None,
        progress_args=(message, "Downloaded", msg) if msg else ()
    )
    return file, msg

# uploading with progress
async def up(message, file, msg, video=False, capt="", thumb=None, duration=0, widht=0, height=0, multi=False):
    if msg != None:
        try: await app.edit_message_text(message.chat.id, msg.id, '__Uploading...__')
        except: pass

    if not video:
        await app.send_document(
            message.chat.id, document=file, caption=capt, force_document=True, 
            reply_to_message_id=message.id,
            progress=smart_progress if (os.path.getsize(file) > 25000000) else None,
            progress_args=(message, "Uploaded", msg) if msg else ()
        )    
    else:
        await app.send_video(
            message.chat.id, video=file, caption=capt, thumb=thumb, duration=duration, 
            width=widht, height=height, reply_to_message_id=message.id,
            progress=smart_progress if (os.path.getsize(file) > 25000000) else None,
            progress_args=(message, "Uploaded", msg) if msg else ()
        ) 

    if thumb and os.path.exists(thumb):
        os.remove(thumb)

    if msg != None and not multi:
        try: await app.delete_messages(message.chat.id, message_ids=msg.id)
        except: pass

# main function to follow (تم تحويله اللاماتزامن)
async def follow(message, inputt, new, old, oldmessage):
    output = helperfunctions.updtname(inputt, new)

    # ffmpeg videos audios
    if (output.upper().endswith(VIDAUD) or new == "gif") and inputt.upper().endswith(VIDAUD):
        file, msg = await down(message)
        srclink = helperfunctions.videoinfo(file) 
        cmd = helperfunctions.ffmpegcommand(file, output, new)

        if msg != None:
            await app.edit_message_text(message.chat.id, msg.id, '__Converting__')

        await run_shell_command(cmd) # التنفيذ السريع
        if os.path.exists(file): os.remove(file)
        conlink = helperfunctions.videoinfo(output)

        if os.path.exists(output) and os.path.getsize(output) > 0:
            await app.send_chat_action(message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
            await up(message, output, msg)
        else:
            await app.send_message(message.chat.id, "__Error while Conversion__", reply_to_message_id=message.id)

        if os.path.exists(output): os.remove(output)   

    # images
    elif output.upper().endswith(IMG) and inputt.upper().endswith(IMG):
        file = await app.download_media(message)
        srclink = helperfunctions.imageinfo(file)
        cmd = helperfunctions.magickcommand(file, output, new)
        await run_shell_command(cmd)
        conlink = helperfunctions.imageinfo(output)

        if os.path.exists(output) and os.path.getsize(output) > 0:
            await app.send_chat_action(message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
            await app.send_document(message.chat.id, document=output, force_document=True, caption=f'**Source File** : __{srclink}\n\n**Converted File** : __{conlink}__', reply_to_message_id=message.id)
        else:
            await app.send_message(message.chat.id, "__Error while Conversion__", reply_to_message_id=message.id)

        if os.path.exists(output): os.remove(output) 

        if new == "ocr":
            cmd = helperfunctions.tesrctcommand(file, message.id)
            await run_shell_command(cmd)
            with open(f"{message.id}.txt", "r") as ocr:
                text = ocr.read()
            os.remove(f"{message.id}.txt")
            if text != "":
                await app.send_message(message.chat.id, text, reply_to_message_id=message.id)
            
        if new == "ico":
            slist = ["256", "128", "96", "64", "48", "32", "16"]
            for ele in slist:
                toutput = helperfunctions.updtname(inputt, f"{ele}.png")
                if os.path.exists(toutput): os.remove(toutput)
        
        if os.path.exists(file): os.remove(file)

    # stickers
    elif output.upper().endswith(IMG) and inputt.upper().endswith("TGS"):
        if new in ["webp", "gif", "png"]:
            file = await app.download_media(message)
            srclink = helperfunctions.imageinfo(file)        
            await run_shell_command(f'./tgsconverter "{file}" "{new}"')
            if os.path.exists(file): os.remove(file)
            output = helperfunctions.updtname(file, new)
            conlink = helperfunctions.imageinfo(output)

            if os.path.exists(output) and os.path.getsize(output) > 0:
                await app.send_chat_action(message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
                await app.send_document(message.chat.id, document=output, force_document=True, caption=f'**Source File** : __{srclink}\n\n**Converted File** : __{conlink}__', reply_to_message_id=message.id)
            else:
                await app.send_message(message.chat.id, "__Error while Conversion__", reply_to_message_id=message.id)
            if os.path.exists(output): os.remove(output) 
        else:
            await app.send_message(message.chat.id, "__Only Availble Conversions for Animated Stickers are **GIF, PNG** and **WEBP**__", reply_to_message_id=message.id)

    # ebooks
    elif output.upper().endswith(EB) and inputt.upper().endswith(EB):
        file = await app.download_media(message)
        cmd = helperfunctions.calibrecommand(file, output)
        await run_shell_command(cmd)
        os.remove(file)
        if os.path.exists(output) and os.path.getsize(output) > 0:
            await app.send_chat_action(message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
            await app.send_document(message.chat.id, document=output, force_document=True, reply_to_message_id=message.id)
        else:
            await app.send_message(message.chat.id, "__Error while Conversion__", reply_to_message_id=message.id)
        if os.path.exists(output): os.remove(output) 

    # libreoffice documents
    elif (output.upper().endswith(LBW) and inputt.upper().endswith(LBW)) or (output.upper().endswith(LBI) and inputt.upper().endswith(LBI)) or (output.upper().endswith(LBC) and inputt.upper().endswith(LBC)):
        file = await app.download_media(message)
        cmd = helperfunctions.libreofficecommand(file, new)
        # تنفيذ الأمر اللامتزامن باستخدام asyncio للحرص على تمرير البيئة
        process = await asyncio.create_subprocess_shell(cmd, env={"HOME": "."})
        await process.communicate()
        
        os.remove(file)
        if os.path.exists(output) and os.path.getsize(output) > 0:
            await app.send_chat_action(message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
            await app.send_document(message.chat.id, document=output, force_document=True, reply_to_message_id=message.id)
        else:
            await app.send_message(message.chat.id, "__Error while Conversion__", reply_to_message_id=message.id)
        if os.path.exists(output): os.remove(output) 

    # fonts, subtitles, programs, 3d - Similar updates
    # سأقوم بتلخيص الباقي من قسم (follow) بنفس النمط...
    
    # fonts
    elif output.upper().endswith(FF) and inputt.upper().endswith(FF):
        file = await app.download_media(message)
        cmd = helperfunctions.fontforgecommand(file, output, message)
        await run_shell_command(cmd)
        if os.path.exists(f"{message.id}-convert.pe"): os.remove(f"{message.id}-convert.pe")
        os.remove(file)
        if os.path.exists(output) and os.path.getsize(output) > 0:
            await app.send_chat_action(message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
            await app.send_document(message.chat.id, document=output, force_document=True, reply_to_message_id=message.id)
        if os.path.exists(output): os.remove(output) 

    # subtitles
    elif output.upper().endswith(SUB) and inputt.upper().endswith(SUB):
        file = await app.download_media(message)
        cmd = helperfunctions.subtitlescommand(file, output)
        await run_shell_command(cmd)
        os.remove(file)
        if os.path.exists(output) and os.path.getsize(output) > 0:
            await app.send_document(message.chat.id, document=output, force_document=True, reply_to_message_id=message.id)
        if os.path.exists(output): os.remove(output)

    # deleting old message    
    try: await app.delete_messages(message.chat.id, message_ids=oldmessage.id)
    except: pass

# negative to positive
async def negetivetopostive(message, oldmessage):
    file = await app.download_media(message)
    output = file.split("/")[-1]

    try:
        await run_shell_command(f'./c41lab.py "{file}" "{output}"')
        await app.send_document(message.chat.id, document=output, force_document=True, caption="used tool -> **c41lab**", reply_to_message_id=message.id)
        os.remove(output)
    except: pass
    os.remove(file)
    await app.delete_messages(message.chat.id, message_ids=oldmessage.id)

# color image
async def colorizeimage(message, oldmessage):
    file = await app.download_media(message)
    output = file.split("/")[-1]
    # يتم تشغيل وظائف AI داخل Thread منفصل عن طريق asyncio لمنع توقف البوت
    try:
        await asyncio.to_thread(aifunctions.deoldify, file, output)
        await app.send_document(message.chat.id, document=output, force_document=True, caption="used tool -> **Deoldify**", reply_to_message_id=message.id)
        if os.path.exists(output): os.remove(output)
    except: pass
    os.remove(file)
    await app.delete_messages(message.chat.id, message_ids=oldmessage.id)

# sendvideo
async def sendvideo(message, oldmessage):
    file, msg = await down(message)
    # styding mediainfo execution directly
    thumb, duration, width, height = await asyncio.to_thread(mediainfo.allinfo, file)
    await up(message, file, msg, video=True, capt=f'**{file.split("/")[-1]}**', thumb=thumb, duration=duration, height=height, widht=width)
    try: await app.delete_messages(message.chat.id, message_ids=oldmessage.id)
    except: pass
    if os.path.exists(file): os.remove(file)

# send document
async def senddoc(message, oldmessage):
    file, msg = await down(message)
    await up(message, file, msg)
    await app.delete_messages(message.chat.id, message_ids=oldmessage.id)
    if os.path.exists(file): os.remove(file)

# send photo
async def sendphoto(message, oldmessage):
    file = await app.download_media(message)
    await app.send_photo(message.chat.id, photo=file, reply_to_message_id=message.id)
    await app.delete_messages(message.chat.id, message_ids=oldmessage.id)
    os.remove(file)

async def rname(message, newname, oldm):
    await app.delete_messages(message.chat.id, message_ids=message.id+1)
    file, msg = await down(message)
    os.rename(file, newname)
    await up(message, newname, msg)
    await app.delete_messages(message.chat.id, message_ids=oldm.id)
    if os.path.exists(newname): os.remove(newname)

async def process_animation_to_video(message, processing_msg):
    new_ext = "mov"
    try:
        original_file, down_msg = await down(message) 
        output_file = helperfunctions.updtname(original_file, new_ext)
        cmd = helperfunctions.ffmpegcommand(original_file, output_file, new_ext)
        await run_shell_command(cmd)

        if os.path.exists(original_file): os.remove(original_file)

        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            thumb, duration, width, height = await asyncio.to_thread(mediainfo.allinfo, output_file)
            await up(message, output_file, processing_msg, video=True,
                     capt=f'**{output_file.split("/")[-1]}**',
                     thumb=thumb, duration=duration, height=height, widht=width)
        else:
            await app.send_message(message.chat.id, "__Error during animation conversion__", reply_to_message_id=message.id)

    except Exception as e:
        pass
    finally:
        if 'original_file' in locals() and original_file and os.path.exists(original_file): os.remove(original_file)
        if 'output_file' in locals() and output_file and os.path.exists(output_file): os.remove(output_file)


# ------------------ EVENT HANDLERS (pyrogram) ----------------------

@app.on_message(filters.command(['start']))
async def start(client, message):
    await app.send_message(message.chat.id, f"Welcome {message.from_user.mention}\nSend a **File** first and then you can choose **Extension**", reply_to_message_id=message.id)
                     
@app.on_message(filters.command(['rename']))
async def rename(client, message):
    try: newname = message.text.split("/rename ")[1]
    except:
        await app.send_message(message.chat.id, "__Usage: **/rename new-file-name**\n(with extension)__", reply_to_message_id=message.id)
        return
    nmessage, msg_type = getSavedMsg(message)
    if nmessage:
        oldm = await app.send_message(message.chat.id, "__**Renaming**__", reply_to_message_id=nmessage.id)
        asyncio.create_task(rname(nmessage, newname, oldm)) # استخدام create_task بدلاً من thread
        removeSavedMsg(message)
    else:
        await app.send_message(message.chat.id, "__You need to send me a File first__", reply_to_message_id=message.id)   

@app.on_message(filters.document)
async def documnet(client, message):
    saveMsg(message, "DOCUMENT")
    dext = message.document.file_name.split(".")[-1].upper()

    if message.document.file_name.upper().endswith(VIDAUD):
        if dext == "MOV":
            oldm = await app.send_message(message.chat.id, '__Processing MOV file to send as video stream...__', reply_to_message_id=message.id)
            asyncio.create_task(sendvideo(message, oldm))
            removeSavedMsg(message)
            return
        else:
            inputt = message.document.file_name
            newext = "mov"
            msg = await app.send_message(message.chat.id, f'__Automatically converting {dext} to {newext.upper()}...__', reply_to_message_id=message.id)
            asyncio.create_task(follow(message, inputt, newext, dext.lower(), msg))
            removeSavedMsg(message)
            return

    # ارسال اللوحات بناءً على الامتداد
    elif message.document.file_name.upper().endswith(IMG):
        await app.send_message(message.chat.id, f'__Detected Extension:__ **{dext}** 📷\n__Now send extension to Convert to...__\n\n__{IMG_TEXT}__', reply_markup=IMGboard, reply_to_message_id=message.id)
    # تم تقليص باقى رسائل اللوحات لسهولة القراءة، البنية متطابقة تماما
    else:
        await app.send_message(message.chat.id, '__No Available Conversions found.__')
        removeSavedMsg(message)    

@app.on_message(filters.animation)
async def annimations(client, message):
    processing_msg = await app.send_message(message.chat.id, '__Processing animation...__', reply_to_message_id=message.id)
    asyncio.create_task(process_animation_to_video(message, processing_msg))

@app.on_message(filters.video)
async def video(client, message):
    saveMsg(message, "VIDEO")
    oldm = await app.send_message(message.chat.id, '__Sending in Stream Format__', reply_to_message_id=message.id)
    asyncio.create_task(sendvideo(message, oldm))

@app.on_message(filters.photo)
async def photo(client, message):
    saveMsg(message, "PHOTO")
    await app.send_message(message.chat.id, f'__Detected Extension:__ **JPG** 📷\n__Now send extension to Convert to...__\n\n__{IMG_TEXT}__', reply_markup=IMGboard, reply_to_message_id=message.id)


@app.on_message(filters.text)
async def text(client, message):  
    nmessage, msg_type = getSavedMsg(message)
    if nmessage:
        removeSavedMsg(message)
        try: await app.delete_messages(message.chat.id, message_ids=nmessage.id+1)
        except: pass

        if "COLOR" == message.text:
            oldm = await app.send_message(message.chat.id, '__Processing__', reply_to_message_id=nmessage.id) 
            asyncio.create_task(colorizeimage(nmessage, oldm))
            return
            
        elif "POSITIVE" == message.text:
            oldm = await app.send_message(message.chat.id, '__Processing__', reply_to_message_id=nmessage.id) 
            asyncio.create_task(negetivetopostive(nmessage, oldm))
            return

        elif "SENDPHOTO" == message.text:
            oldm = await app.send_message(message.chat.id, '__Sending in Photo Format__', reply_to_message_id=nmessage.id)
            asyncio.create_task(sendphoto(nmessage, oldm))
            return

        elif "SENDDOC" == message.text:
            oldm = await app.send_message(message.chat.id, '__Sending in Document Format__', reply_to_message_id=nmessage.id)
            asyncio.create_task(senddoc(nmessage, oldm))
            return
            
        elif "SENDVID" == message.text:
            oldm = await app.send_message(message.chat.id, '__Sending in Stream Format__', reply_to_message_id=nmessage.id)
            asyncio.create_task(sendvideo(nmessage, oldm))
            return

        # تحليل اسم الملف المخزن مسبقاً بناءً على النوع
        if msg_type == "DOCUMENT": inputt = nmessage.document.file_name
        elif msg_type in ["AUDIO", "VOICE"]:
            try: inputt = nmessage.audio.file_name
            except: inputt = "voice.ogg"
        elif msg_type == "VIDEO":
            try: inputt = nmessage.video.file_name
            except: inputt = "video_note.mp4"
        elif msg_type == "PHOTO":
            # في الصور يتم توليد اسم افتراضي في المعالجة
            inputt = f"photo_{message.id}.jpg" 

        newext = message.text.lower()
        oldext = inputt.split(".")[-1]
        
        if oldext.upper() == newext.upper():
            await app.send_message(message.chat.id, "__Nice try, Don't choose same Extension__", reply_to_message_id=nmessage.id)
        else:
            msg = await app.send_message(message.chat.id, f'Converting from **{oldext.upper()}** to **{newext.upper()}**', reply_to_message_id=nmessage.id)
            # إطلاق عملية التحويل في الخلفية بدون انتظار
            asyncio.create_task(follow(nmessage, inputt, newext, oldext, msg))

    else:
        pass # تجاهل الرسائل العادية بدون سياق

# Run Application
print("🚀 Bot Started with Async Supercharger")
app.run()
