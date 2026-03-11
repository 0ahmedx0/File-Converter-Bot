import pyrogram
from pyrogram import Client
from pyrogram import filters
from pyrogram import enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from pyrogram.errors import FloodWait, PeerIdInvalid
import os
import shutil
import subprocess
import threading
import time
import queue
# مكتبة بايثون للصور بديلة لـ imagemagick
from PIL import Image
from buttons import *
import helperfunctions
import mediainfo
import guess
import tormag
import progconv
import others
import tictactoe

# --- إعدادات البيئة ---
bot_token = os.environ.get("TOKEN", "")
api_hash = os.environ.get("HASH", "")
api_id = os.environ.get("ID", "")

# --- إعدادات الحماية من الحظر (Flood Protection) ---
MAX_CONCURRENT_TASKS = 3
task_semaphore = threading.Semaphore(MAX_CONCURRENT_TASKS)

# --- تهيئة البوت ---
app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)
MESGS = {}

# تتبع الفيديوهات برقم الرسالة بدلا من المستخدم لمنع التداخل
SS_STATES = {}
# تتبع طباعة سطر الأوامر لمنع الضغط والتكرار المزعج
PROGRESS_TRACKER = {}

# --- دوال مساعدة لإدارة الرسائل ---
def saveMsg(msg, msg_type):
    MESGS[msg.from_user.id] = [msg, msg_type]

def getSavedMsg(msg):
    return MESGS.get(msg.from_user.id, [None, None])

def removeSavedMsg(msg):
    MESGS.pop(msg.from_user.id, None)

# --- دالة الأمان للاتصال بتليجرام (Safe Call Wrapper) ---
def safe_app_call(func, *args, max_retries=3, **kwargs):
    attempt = 0
    while attempt < max_retries:
        try:
            return func(*args, **kwargs)
        except FloodWait as e:
            wait_time = e.value
            print(f"⚠️ FloodWait detected! Waiting for {wait_time} seconds...")
            time.sleep(wait_time)
            attempt += 1
        except PeerIdInvalid:
            print("❌ PeerIdInvalid: User blocked bot or chat invalid.")
            return None
        except Exception as e:
            print(f"❌ Error in safe_app_call: {e}")
            return None
    return None

# --- دوال التنزيل والرفع ومراقبة التقدم المعدلة ---
def down(message):
    # اظهار رسالة التنزيل دائماً مهما كان حجم الملف
    msg = safe_app_call(app.send_message, message.chat.id, '📥 __جاري بدء التحميل... 0%__', reply_to_message_id=message.id)
    if msg:
        dosta = threading.Thread(target=lambda: downstatus(f'{message.id}downstatus.txt', msg), daemon=True)
        dosta.start()
    
    try:
        file = app.download_media(message, progress=dprogress, progress_args=[message])
        if os.path.exists(f'{message.id}downstatus.txt'):
            os.remove(f'{message.id}downstatus.txt')
        return file, msg
    except FloodWait as e:
        print(f"⚠️ Download FloodWait: {e.value}s")
        time.sleep(e.value)
        return down(message)
    except Exception as e:
        print(f"❌ Download Error: {e}")
        return None, None

def up(message, file, msg, video=False, capt="", thumb=None, duration=0, widht=0, height=0, multi=False):
    if msg is not None:
        try:
            safe_app_call(app.edit_message_text, message.chat.id, msg.id, '📤 __جاري بدء الرفع... 0%__')
        except:
            pass
    
    # اظهار نسبة الرفع دائماً مهما كان حجم الملف
    upsta = threading.Thread(target=lambda: upstatus(f'{message.id}upstatus.txt', msg), daemon=True)
    upsta.start()
    
    try:
        if not video:
            safe_app_call(app.send_document, message.chat.id, document=file, caption=capt, force_document=True,
                          reply_to_message_id=message.id, progress=uprogress, progress_args=[message])
        else:
            safe_app_call(app.send_video, message.chat.id, video=file, caption=capt, thumb=thumb, duration=duration,
                          width=widht, height=height, reply_to_message_id=message.id,
                          progress=uprogress, progress_args=[message])
    except FloodWait as e:
        print(f"⚠️ Upload FloodWait: {e.value}s")
        time.sleep(e.value)
        up(message, file, msg, video, capt, thumb, duration, widht, height, multi)
    except Exception as e:
        print(f"❌ Upload Error: {e}")
    finally:
        if thumb is not None and os.path.exists(thumb):
            os.remove(thumb)
        if os.path.exists(f'{message.id}upstatus.txt'):
            os.remove(f'{message.id}upstatus.txt')
        if msg is not None and not multi:
            try:
                safe_app_call(app.delete_messages, message.chat.id, message_ids=msg.id)
            except:
                pass

# --- دوال التقدم الجديدة (نسبة وتيرمنال) ---
def uprogress(current, total, message):
    percent = (current * 100 / total) if total else 0
    now = time.time()
    last_time = PROGRESS_TRACKER.get(f"u_{message.id}", 0)
    
    try:
        with open(f'{message.id}upstatus.txt', "w") as fileup:
            fileup.write(f"{percent:.1f}%")
    except:
        pass
        
    if now - last_time > 2.0 or current == total:
        print(f"📤 رفع [رسالة: {message.id}] - نسبة: {percent:.1f}%  ({current}/{total} B)")
        PROGRESS_TRACKER[f"u_{message.id}"] = now

def dprogress(current, total, message):
    percent = (current * 100 / total) if total else 0
    now = time.time()
    last_time = PROGRESS_TRACKER.get(f"d_{message.id}", 0)
    
    try:
        with open(f'{message.id}downstatus.txt', "w") as fileup:
            fileup.write(f"{percent:.1f}%")
    except:
        pass
        
    if now - last_time > 2.0 or current == total:
        print(f"📥 تنزيل [رسالة: {message.id}] - نسبة: {percent:.1f}%  ({current}/{total} B)")
        PROGRESS_TRACKER[f"d_{message.id}"] = now

def upstatus(statusfile, message):
    while True:
        if os.path.exists(statusfile):
            break
        time.sleep(1)
    while os.path.exists(statusfile):
        try:
            with open(statusfile, "r") as upread:
                txt = upread.read()
            if txt:
                safe_app_call(app.edit_message_text, message.chat.id, message.id, f"📤 __جاري الرفع__ : **{txt}**")
            time.sleep(4)
        except FloodWait as e:
            time.sleep(e.value)
        except:
            time.sleep(2)

def downstatus(statusfile, message):
    while True:
        if os.path.exists(statusfile):
            break
        time.sleep(1)
    while os.path.exists(statusfile):
        try:
            with open(statusfile, "r") as upread:
                txt = upread.read()
            if txt:
                safe_app_call(app.edit_message_text, message.chat.id, message.id, f"📥 __جاري التنزيل__ : **{txt}**")
            time.sleep(4)
        except FloodWait as e:
            time.sleep(e.value)
        except:
            time.sleep(2)

# --- دوال لقطات الشاشة والألبوم الأوتوماتيكية ---
def get_video_duration(filepath):
    try:
        cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{filepath}"'
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Error getting duration via ffprobe: {e}")
        return None

def download_and_ask_video(message, msg):
    file, down_msg = down(message)
    if not file:
        safe_app_call(app.edit_message_text, message.chat.id, msg.id, "❌ __فشل تحميل الفيديو.__")
        return
    
    display_msg = down_msg if down_msg else msg
    prompt_msg_id = display_msg.id
    
    SS_STATES[prompt_msg_id] = {"video_file": file, "video_msg": message, "user_id": message.from_user.id}
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 استخراج لقطات شاشة بدقة عالية", callback_data="ASK_SS")],
        [InlineKeyboardButton("🎥 الإرسال كبث عادي (Stream)", callback_data="DO_STREAM_FILE")]
    ])
    
    safe_app_call(app.edit_message_text, message.chat.id, prompt_msg_id, 
                  '✅ **تم الانتهاء من تحميل الفيديو.**\n\n__اختر الإجراء الذي تريده:__', 
                  reply_markup=markup)

def execute_screenshots(file, count, status_msg, prompt_msg_id, user_id, chat_id):
    try:
        duration = get_video_duration(file)
        if not duration:
            try:
                _, dur, _, _ = mediainfo.allinfo(file)
                duration = float(dur)
            except:
                duration = 60.0
        
        images = []
        interval = duration / (count + 1)
        
        for i in range(1, count + 1):
            timestamp = interval * i
            out_img = f"ss_{user_id}_{prompt_msg_id}_{i}.jpg"
            cmd = f'ffmpeg -y -ss {timestamp} -i "{file}" -vframes 1 -q:v 1 "{out_img}"'
            os.system(cmd)
            
            if os.path.exists(out_img) and os.path.getsize(out_img) > 0:
                images.append(out_img)

        if os.path.exists(file):
            os.remove(file) 

        if not images:
            safe_app_call(app.edit_message_text, status_msg.chat.id, status_msg.id, "❌ __فشل استخراج لقطات الشاشة.__")
            SS_STATES.pop(prompt_msg_id, None)
            return

        if prompt_msg_id in SS_STATES:
            SS_STATES[prompt_msg_id]["images"] = images

            safe_app_call(app.edit_message_text, status_msg.chat.id, status_msg.id, 
                          f"✅ __تم استخراج **{len(images)}** لقطة بنجاح!__\n\n📤 __جاري الرفع التلقائي كألبومات...__")
            
            user_data = SS_STATES.get(prompt_msg_id)
            ul_thread = threading.Thread(target=lambda: upload_screenshots(chat_id, prompt_msg_id, user_data, status_msg), daemon=True)
            ul_thread.start()

    except Exception as e:
        print(f"Screenshot Extraction Error: {e}")
        safe_app_call(app.edit_message_text, status_msg.chat.id, status_msg.id, f"❌ __حدث خطأ أثناء الاستخراج: {e}__")
        if file and os.path.exists(file): os.remove(file)
        SS_STATES.pop(prompt_msg_id, None)

def upload_screenshots(chat_id, prompt_msg_id, user_data, msg):
    images = user_data.get("images", [])
    if not images: return
    
    try:
        media_chunks = [images[i:i + 10] for i in range(0, len(images), 10)]
        for index, chunk in enumerate(media_chunks):
            if len(chunk) == 1:
                safe_app_call(app.send_photo, chat_id, photo=chunk[0])
            else:
                media_group = [InputMediaPhoto(img) for img in chunk]
                try:
                    safe_app_call(app.send_media_group, chat_id, media=media_group)
                except FloodWait as e:
                    time.sleep(e.value)
                    safe_app_call(app.send_media_group, chat_id, media=media_group)
            
            time.sleep(2.5)

        safe_app_call(app.delete_messages, chat_id, msg.id)
        
    except Exception as e:
        print(f"Album upload error: {e}")
        for img in images:
            safe_app_call(app.send_photo, chat_id, photo=img)
            time.sleep(1)
        try: safe_app_call(app.delete_messages, chat_id, msg.id)
        except: pass
    finally:
        for img in images:
            if os.path.exists(img):
                os.remove(img)
        SS_STATES.pop(prompt_msg_id, None)


# --- الدالة الرئيسية للمعالجة القديمة الخاصة بالبوت ---
def follow(message, inputt, new, old, oldmessage):
    with task_semaphore:
        output = helperfunctions.updtname(inputt, new)
        try:
            # ffmpeg videos audios
            if (output.upper().endswith(VIDAUD) or new == "gif") and inputt.upper().endswith(VIDAUD):
                print("It is VID/AUD option")
                file, msg = down(message)
                if not file:
                    safe_app_call(app.send_message, message.chat.id, "__Error: Download Failed__", reply_to_message_id=message.id)
                    return

                srclink = helperfunctions.videoinfo(file)
                cmd = helperfunctions.ffmpegcommand(file, output, new)
                if msg is not None:
                    safe_app_call(app.edit_message_text, message.chat.id, msg.id, '__Converting__')
                
                os.system(cmd)
                if os.path.exists(file):
                    os.remove(file)
                
                conlink = helperfunctions.videoinfo(output)
                if os.path.exists(output) and os.path.getsize(output) > 0:
                    safe_app_call(app.send_chat_action, message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
                    up(message, output, msg)
                else:
                    safe_app_call(app.send_message, message.chat.id, "__Error while Conversion__", reply_to_message_id=message.id)
                if os.path.exists(output):
                    os.remove(output)

            # images 
            elif output.upper().endswith(IMG) and inputt.upper().endswith(IMG):
                print("It is IMG option")
                file = None
                try:
                    file = app.download_media(message)
                    if not file or not os.path.exists(file):
                        safe_app_call(app.send_message, message.chat.id, "__Error: File download failed__", reply_to_message_id=message.id)
                        return

                    with Image.open(file) as img:
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGBA")
                        else:
                            img = img.convert("RGB")
                        img.save(output, format='PNG')
                    
                    if os.path.exists(output) and os.path.getsize(output) > 0:
                        safe_app_call(app.send_chat_action, message.chat.id, enums.ChatAction.UPLOAD_PHOTO)
                        safe_app_call(app.send_photo, message.chat.id, photo=output,
                                      caption=f'**Converted File** : __{output}__', reply_to_message_id=message.id)
                    else:
                        safe_app_call(app.send_message, message.chat.id, "__Error while Conversion__", reply_to_message_id=message.id)
                        
                except Exception as e:
                    print(f"❌ Pillow Error: {e}")
                    safe_app_call(app.send_message, message.chat.id, f"__Error: {str(e)}__", reply_to_message_id=message.id)
                finally:
                    if file and os.path.exists(file):
                        os.remove(file)
                    if os.path.exists(output):
                        os.remove(output)

            # stickers
            elif output.upper().endswith(IMG) and inputt.upper().endswith("TGS"):
                if new == "webp" or new == "gif" or new == "png":
                    print("It is Animated Sticker option")
                    file = app.download_media(message)
                    if not file: return
                    
                    srclink = helperfunctions.imageinfo(file)
                    os.system(f'./tgsconverter "{file}" "{new}"')
                    if os.path.exists(file):
                        os.remove(file)
                    
                    output = helperfunctions.updtname(file, new)
                    conlink = helperfunctions.imageinfo(output)
                    if os.path.exists(output) and os.path.getsize(output) > 0:
                        safe_app_call(app.send_chat_action, message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
                        safe_app_call(app.send_document, message.chat.id, document=output, force_document=True,
                                      caption=f'**Source File** : __{srclink}\n**Converted File** : __{conlink}__',
                                      reply_to_message_id=message.id)
                    else:
                        safe_app_call(app.send_message, message.chat.id, "__Error while Conversion__", reply_to_message_id=message.id)
                    if os.path.exists(output):
                        os.remove(output)
                else:
                    safe_app_call(app.send_message, message.chat.id,
                                  "__Only Availble Conversions for Animated Stickers are **GIF, PNG** and **WEBP**__",
                                  reply_to_message_id=message.id)

            # ebooks
            elif output.upper().endswith(EB) and inputt.upper().endswith(EB):
                print("It is Ebook option")
                file = app.download_media(message)
                if not file: return
                cmd = helperfunctions.calibrecommand(file, output)
                os.system(cmd)
                if os.path.exists(file):
                    os.remove(file)
                if os.path.exists(output) and os.path.getsize(output) > 0:
                    safe_app_call(app.send_chat_action, message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
                    safe_app_call(app.send_document, message.chat.id, document=output, force_document=True,
                                  reply_to_message_id=message.id)
                else:
                    safe_app_call(app.send_message, message.chat.id, "__Error while Conversion__", reply_to_message_id=message.id)
                if os.path.exists(output):
                    os.remove(output)

            # libreoffice documents
            elif (output.upper().endswith(LBW) and inputt.upper().endswith(LBW)) or \
                 (output.upper().endswith(LBI) and inputt.upper().endswith(LBI)) or \
                 (output.upper().endswith(LBC) and inputt.upper().endswith(LBC)):
                print("It is LibreOffice option")
                file = app.download_media(message)
                if not file: return
                cmd = helperfunctions.libreofficecommand(file, new)
                try:
                    subprocess.run([cmd], env={"HOME": "."})
                except Exception as e:
                    print(f"LibreOffice Error: {e}")
                if os.path.exists(file):
                    os.remove(file)
                if os.path.exists(output) and os.path.getsize(output) > 0:
                    safe_app_call(app.send_chat_action, message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
                    safe_app_call(app.send_document, message.chat.id, document=output, force_document=True,
                                  reply_to_message_id=message.id)
                else:
                    safe_app_call(app.send_message, message.chat.id, "__Error while Conversion__", reply_to_message_id=message.id)
                if os.path.exists(output):
                    os.remove(output)

            # fonts
            elif output.upper().endswith(FF) and inputt.upper().endswith(FF):
                print("It is FontForge option")
                file = app.download_media(message)
                if not file: return
                cmd = helperfunctions.fontforgecommand(file, output, message)
                os.system(cmd)
                if os.path.exists(f"{message.id}-convert.pe"):
                    os.remove(f"{message.id}-convert.pe")
                if os.path.exists(file):
                    os.remove(file)
                if os.path.exists(output) and os.path.getsize(output) > 0:
                    safe_app_call(app.send_chat_action, message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
                    safe_app_call(app.send_document, message.chat.id, document=output, force_document=True,
                                  reply_to_message_id=message.id)
                else:
                    safe_app_call(app.send_message, message.chat.id, "__Error while Conversion__", reply_to_message_id=message.id)
                if os.path.exists(output):
                    os.remove(output)

            # subtitles
            elif output.upper().endswith(SUB) and inputt.upper().endswith(SUB):
                if not ((old.upper() in ["TTML", "SCC", "SRT"]) and (new.upper() in ["TTML", "SRT", "VTT"])):
                    safe_app_call(app.send_message, message.chat.id,
                                  f"__**{old.upper()}** to **{new.upper()}** is not Supported.__",
                                  reply_to_message_id=message.id)
                else:
                    print("It is Subtitles option")
                    file = app.download_media(message)
                    if not file: return
                    cmd = helperfunctions.subtitlescommand(file, output)
                    os.system(cmd)
                    if os.path.exists(file):
                        os.remove(file)
                    if os.path.exists(output) and os.path.getsize(output) > 0:
                        safe_app_call(app.send_chat_action, message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
                        safe_app_call(app.send_document, message.chat.id, document=output, force_document=True,
                                      reply_to_message_id=message.id)
                    else:
                        safe_app_call(app.send_message, message.chat.id, "__Error while Conversion__", reply_to_message_id=message.id)
                    if os.path.exists(output):
                        os.remove(output)

            # programs
            elif output.upper().endswith(PRO) and inputt.upper().endswith(PRO):
                flag = 0
                lang = ""
                if ((old.upper() == "C") and (new.upper() == "GO")):
                    flag = 1
                elif ((old.upper() == "PY") and (new.upper() in ['CPP','RS','JL','KT','NIM','DART','GO'])):
                    flag = 2
                    extens = ['CPP','RS','JL','KT','NIM','DART','GO']
                    langs = ['cpp','rust','julia','kotlin','nim','dart','go']
                    for i in range(len(langs)):
                        if new.upper() == extens[i]:
                            lang = langs[i]
                elif ((old.upper() == "JAVA") and (new.upper() in ["JS","TS"])):
                    flag = 3
                    lang = new.upper()
                
                if not flag:
                    app.send_message(message.chat.id,
                                     f"__**{old.upper()}** to **{new.upper()}** is not Supported.\n\n**Supported Formats:**\nC -> GO\nPY -> CPP, RS, JL, KT, NIM, DART & GO\nJAVA -> JS & TS__",
                                     reply_to_message_id=message.id)
                else:
                    print("It is Programs option")
                    file = app.download_media(message)
                    if not file:
                        return
                    if flag == 1:
                        output = progconv.c2Go(file)
                    elif flag == 2:
                        output = progconv.py2Many(file, lang)
                    elif flag == 3:
                        with open(file, "r") as jfile:
                            javacode = jfile.read()
                        info = progconv.java2JSandTS(javacode, lang)
                        if info[0] == 1:
                            with open(output, "w") as pfile:
                                pfile.write(info[1])
                        else:
                            errormessage = ""
                            for ele in info[1]:
                                errormessage = errormessage + ele + "\n"
                    os.remove(file)
                    if os.path.exists(output) and os.path.getsize(output) > 0:
                        app.send_chat_action(message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
                        app.send_document(message.chat.id, document=output, force_document=True,
                                          reply_to_message_id=message.id)
                    else:
                        if flag != 3:
                            errormessage = "Error while Conversion"
                        app.send_message(message.chat.id, f"__{errormessage}__", reply_to_message_id=message.id)
                    if os.path.exists(output):
                        os.remove(output)
            # 3D files
            elif output.upper().endswith(T3D) and inputt.upper().endswith(T3D):
                if (old.upper() == "WRL"):
                    safe_app_call(app.send_message, message.chat.id,
                                  f"__**{old.upper()}** is Export Only, cannot be used to Convert from__",
                                  reply_to_message_id=message.id)
                else:
                    print("It is 3D files option")
                    file = app.download_media(message)
                    if not file: return
                    cmd = helperfunctions.ctm3dcommand(file, output)
                    os.system(cmd)
                    if os.path.exists(file):
                        os.remove(file)
                    if os.path.exists(output) and os.path.getsize(output) > 0:
                        safe_app_call(app.send_chat_action, message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
                        safe_app_call(app.send_document, message.chat.id, document=output, force_document=True,
                                      reply_to_message_id=message.id)
                    else:
                        safe_app_call(app.send_message, message.chat.id, "__Error while Conversion__", reply_to_message_id=message.id)
                    if os.path.exists(output):
                        os.remove(output)
            
            else:
                safe_app_call(app.send_message, message.chat.id, "__Choose a Valid Extension, don't Type it__", reply_to_message_id=message.id)

            try:
                safe_app_call(app.delete_messages, message.chat.id, message_ids=oldmessage.id)
            except:
                pass

        except Exception as e:
            print(f"❌ Critical Error in follow: {e}")
            safe_app_call(app.send_message, message.chat.id, f"__Critical Error: {str(e)}__", reply_to_message_id=message.id)

# --- باقي الدوال والميزات الأصلية الخاصة بالبوت ---
def negetivetopostive(message, oldmessage):
    file = app.download_media(message)
    output = file.split("/")[-1]
    try:
        print("using c41lab")
        os.system(f'./c41lab.py "{file}" "{output}"')
        safe_app_call(app.send_document, message.chat.id, document=output, force_document=True,
                      caption="used tool -> **c41lab**", reply_to_message_id=message.id)
        os.remove(output)
    except: pass
    try:
        print("using simple tool")
        safe_app_call(app.send_document, message.chat.id, document=output, force_document=True,
                      caption="used tool -> **openCV**", reply_to_message_id=message.id)
        os.remove(output)
    except: pass
    try:
        print("using negfix8")
        os.system(f'./negfix8 "{file}" "{output}"')
        safe_app_call(app.send_document, message.chat.id, document=output, force_document=True,
                      caption="used tool -> **negfix8**", reply_to_message_id=message.id)
        os.remove(output)
    except: pass
    if os.path.exists(file): os.remove(file)
    safe_app_call(app.delete_messages, message.chat.id, message_ids=oldmessage.id)

def colorizeimage(message, oldmessage):
    file = app.download_media(message)
    output = file.split("/")[-1]
    try:
        safe_app_call(app.send_document, message.chat.id, document=output, force_document=True,
                      caption="used tool -> **Deoldify**", reply_to_message_id=message.id)
        os.remove(output)
    except: pass
    try:
        safe_app_call(app.send_document, message.chat.id, document=output, force_document=True,
                      caption="used tool -> **Local Model**", reply_to_message_id=message.id)
        os.remove(output)
    except: pass
    if os.path.exists(file): os.remove(file)
    safe_app_call(app.delete_messages, message.chat.id, message_ids=oldmessage.id)

def genrateimages(message, prompt, msg):
    try:
        safe_app_call(app.delete_messages, message.chat.id, message_ids=msg.id)
    except Exception as e: pass

def genratemusic(message, prompt, msg):
    try:
        safe_app_call(app.delete_messages, message.chat.id, message_ids=msg.id)
    except Exception as e: pass

def genratevideos(message, prompt): pass

def dltmsg(umsg, rmsg, sec=15):
    time.sleep(sec)
    try:
        safe_app_call(app.delete_messages, umsg.chat.id, message_ids=[umsg.id, rmsg.id])
    except FloodWait as e:
        time.sleep(e.value)
    except: pass

def readf(message, oldmessage):
    file = app.download_media(message)
    try:
        with open(file, "r", encoding="utf-8") as rf:
            txt = rf.read()
        n = 4096
        split = [txt[i:i+n] for i in range(0, len(txt), n)]
        if len(split) > 10:
            safe_app_call(app.send_message, message.chat.id, "__File Contents is too Long__", reply_to_message_id=message.id)
            return
        for ele in split:
            safe_app_call(app.send_message, message.chat.id, ele, disable_web_page_preview=True, reply_to_message_id=message.id)
            time.sleep(3)
    except Exception as e:
        safe_app_call(app.send_message, message.chat.id, f"__Error in Reading File : {e}__", reply_to_message_id=message.id)
    finally:
        if os.path.exists(file): os.remove(file)
        try: safe_app_call(app.delete_messages, message.chat.id, message_ids=oldmessage.id)
        except: pass

def send_local_video(original_message, local_video_path, processing_msg):
    try:
        thumb, duration, width, height = mediainfo.allinfo(local_video_path)
        up(original_message, local_video_path, processing_msg, video=True,
           capt=f'**{local_video_path.split("/")[-1]}**',
           thumb=thumb, duration=duration, height=height, widht=width)
    except Exception as e:
        try:
            safe_app_call(app.send_message, original_message.chat.id, f"__Error sending converted video: {e}__", reply_to_message_id=original_message.id)
            if processing_msg: safe_app_call(app.delete_messages, original_message.chat.id, message_ids=processing_msg.id)
        except: pass
    finally:
        if os.path.exists(local_video_path): os.remove(local_video_path)

def sendvideo(message, oldmessage):
    file, msg = down(message)
    if not file: return
    thumb, duration, width, height = mediainfo.allinfo(file)
    up(message, file, msg, video=True, capt=f'**{file.split("/")[-1]}**', thumb=thumb, duration=duration, height=height, widht=width)
    try: safe_app_call(app.delete_messages, message.chat.id, message_ids=oldmessage.id)
    except: pass
    if os.path.exists(file): os.remove(file)

def senddoc(message, oldmessage):
    file, msg = down(message)
    if not file: return
    up(message, file, msg)
    try: safe_app_call(app.delete_messages, message.chat.id, message_ids=oldmessage.id)
    except: pass
    if os.path.exists(file): os.remove(file)

def sendphoto(message, oldmessage):
    file = app.download_media(message)
    if not file: return
    safe_app_call(app.send_photo, message.chat.id, photo=file, reply_to_message_id=message.id)
    try: safe_app_call(app.delete_messages, message.chat.id, message_ids=oldmessage.id)
    except: pass
    if os.path.exists(file): os.remove(file)

def extract(message, oldm):
    file, msg = down(message)
    if not file: return
    cmd, foldername, infofile = helperfunctions.zipcommand(file, message)
    if msg is not None:
        safe_app_call(app.edit_message_text, message.chat.id, msg.id, '__Extracting__')
    os.system(cmd)
    os.remove(file)
    with open(infofile, 'r') as f:
        lines = f.read()
    last = lines.split("Everything is Ok\n")[-1].replace("      ", "")
    os.remove(infofile)
    if os.path.exists(foldername):
        dir_list = helperfunctions.absoluteFilePaths(foldername)
        if len(dir_list) > 30:
            if msg is not None: safe_app_call(app.delete_messages, message.chat.id, message_ids=msg.id)
            safe_app_call(app.send_message, message.chat.id, f"__Number of files is **{len(dir_list)}** which is more than the limit of **30**__", reply_to_message_id=message.id)
        else:
            for ele in dir_list:
                if os.path.getsize(ele) > 0:
                    up(message, ele, msg, multi=True)
                    os.remove(ele)
                else:
                    safe_app_call(app.send_message, message.chat.id, f'**{ele.split("/")[-1]}** __is Skipped because it is 0 bytes__', reply_to_message_id=message.id)
            if msg is not None: safe_app_call(app.delete_messages, message.chat.id, message_ids=msg.id)
            safe_app_call(app.send_message, message.chat.id, f'__{last}__', reply_to_message_id=message.id)
        shutil.rmtree(foldername)
    else:
        safe_app_call(app.send_message, message.chat.id, "**Unable to Extract**", reply_to_message_id=message.id)
    safe_app_call(app.delete_messages, message.chat.id, message_ids=oldm.id)

def getmag(message, oldm):
    file = app.download_media(message)
    if not file: return
    maglink = tormag.getMagnet(file)
    safe_app_call(app.send_message, message.chat.id, f'__{maglink}__', reply_to_message_id=message.id)
    safe_app_call(app.delete_messages, message.chat.id, message_ids=oldm.id)
    os.remove(file)

def gettorfile(message, oldm):
    file = tormag.getTorFile(message.text)
    safe_app_call(app.send_document, message.chat.id, file, reply_to_message_id=message.id)
    safe_app_call(app.delete_messages, message.chat.id, message_ids=oldm.id)
    os.remove(file)

def compile(message, oldm):
    ext = message.document.file_name.split(".")[-1]
    if ext.upper() == "JAR":
        file = app.download_media(message)
        cmd, folder, files = helperfunctions.warpcommand(file, message)
        os.system(cmd)
        if not os.path.exists(folder):
            cmd, folder, files = helperfunctions.warpcommand(file, message, True)
            os.system(cmd)
        os.remove(file)
        if os.path.exists(folder):
            safe_app_call(app.send_chat_action, message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
            for ele in files:
                if os.path.exists(ele) and os.path.getsize(ele) > 0:
                    safe_app_call(app.send_document, message.chat.id, document=ele, force_document=True, reply_to_message_id=message.id)
                    os.remove(ele)
            shutil.rmtree(folder)
        else:
            safe_app_call(app.send_message, message.chat.id, "__Error while Compiling__", reply_to_message_id=message.id)
    elif ext.upper() in ['C', 'CPP']:
        file = app.download_media(message)
        cmd, output = helperfunctions.gppcommand(file)
        os.system(cmd)
        os.remove(file)
        if os.path.exists(output) and os.path.getsize(output) > 0:
            safe_app_call(app.send_document, message.chat.id, document=output, caption="__Linux Executable__", force_document=True, reply_to_message_id=message.id)
            os.remove(output)
        else:
            safe_app_call(app.send_message, message.chat.id, "__Error while Compiling__", reply_to_message_id=message.id)
    elif ext.upper() == "PY":
        file = app.download_media(message)
        cmd, output, ofold, tfold, temp = helperfunctions.pyinstallcommand(message, file)
        os.system(cmd)
        os.remove(file)
        if os.path.exists(output) and os.path.getsize(output) > 0:
            safe_app_call(app.send_document, message.chat.id, document=output, caption="__Linux Executable__", force_document=True, reply_to_message_id=message.id)
            os.remove(output)
        else:
            safe_app_call(app.send_message, message.chat.id, "__Error while Compiling__", reply_to_message_id=message.id)
        if os.path.exists(temp): os.remove(temp)
        if os.path.exists(ofold): shutil.rmtree(ofold)
        if os.path.exists(tfold): shutil.rmtree(tfold)
    else:
        safe_app_call(app.send_message, message.chat.id, "__At this time Compilation only supports from JAR, PY, C and CPP Files__", reply_to_message_id=message.id)
    safe_app_call(app.delete_messages, message.chat.id, message_ids=oldm.id)

def runpro(message, oldm):
    ext = message.document.file_name.split(".")[-1]
    if ext.upper() == "PY":
        file = app.download_media(message)
        code = open(file, "r", encoding="utf-8").read()
        os.remove(file)
        info = others.pyrun(code)
        safe_app_call(app.send_message, message.chat.id, info, reply_to_message_id=message.id)
        safe_app_call(app.delete_messages, message.chat.id, message_ids=oldm.id)
    else:
        safe_app_call(app.send_message, message.chat.id, "__At this time Running only supports from PY Files__", reply_to_message_id=message.id)

def bgremove(message, oldm):
    file = app.download_media(message)
    if not file: return
    os.remove(file)
    safe_app_call(app.delete_messages, message.chat.id, message_ids=oldm.id)

def scan(message, oldm):
    file = app.download_media(message)
    if not file: return
    info = helperfunctions.scanner(file)
    safe_app_call(app.send_message, message.chat.id, f"__{info}__", reply_to_message_id=message.id)
    safe_app_call(app.delete_messages, message.chat.id, message_ids=oldm.id)
    os.remove(file)

def makefile(message, mtext, oldmessage):
    text = mtext.split("\n")
    if len(text) == 1:
        safe_app_call(app.send_message, message.chat.id, "__Make-File takes First line of your Text as Filename and File content will start from Second line__", reply_to_message_id=message.id)
        return
    firstline = text[0]
    firstline = "".join(x for x in firstline if (x.isalnum() or x in "._-@ "))
    text.remove(text[0])
    mtext = ""
    for ele in text:
        mtext = mtext + f"{ele}\n"
    with open(firstline, "w") as file:
        file.write(mtext)
    if os.path.exists(firstline) and os.path.getsize(firstline) > 0:
        safe_app_call(app.send_document, message.chat.id, document=firstline, reply_to_message_id=message.id)
    else:
        safe_app_call(app.send_message, message.chat.id, "__Error while making file__", reply_to_message_id=message.id)
    safe_app_call(app.delete_messages, message.chat.id, message_ids=oldmessage.id)
    os.remove(firstline)

def transcript(message, oldmessage):
    file = app.download_media(message)
    if not file: return
    inputt = file.split("/")[-1]
    output = helperfunctions.updtname(inputt, "wav")
    temp = helperfunctions.updtname(inputt, "txt")
    if file.endswith("wav"): pass
    else:
        cmd = helperfunctions.ffmpegcommand(file, output, "wav")
        os.system(cmd)
        os.remove(output)
    if os.path.getsize(temp) > 0:
        safe_app_call(app.send_document, message.chat.id, document=temp, caption="**Google Engine**", reply_to_message_id=message.id)
        os.remove(temp)
    safe_app_call(app.delete_messages, message.chat.id, message_ids=oldmessage.id)
    os.remove(file)

def textTo3d(prompt, message, msg):
    try: safe_app_call(app.delete_messages, message.chat.id, message_ids=msg.id)
    except Exception as e: pass

def speak(message, oldmessage):
    file = app.download_media(message)
    if not file: return
    inputt = file.split("/")[-1]
    output = helperfunctions.updtname(inputt, "mp3")
    os.remove(file)
    safe_app_call(app.send_document, message.chat.id, document=output, reply_to_message_id=message.id)
    safe_app_call(app.delete_messages, message.chat.id, message_ids=oldmessage.id)
    os.remove(output)

def increaseres(message, oldmessage):
    file = app.download_media(message)
    if not file: return
    inputt = file.split("/")[-1]
    try:
        os.remove(file)
        safe_app_call(app.send_document, message.chat.id, document=inputt, reply_to_message_id=message.id)
    except Exception as e:
        safe_app_call(app.send_message, message.chat.id, f"__Error : {e}__", reply_to_message_id=message.id)
    safe_app_call(app.delete_messages, message.chat.id, message_ids=oldmessage.id)
    os.remove(inputt)

def rname(message, newname, oldm):
    safe_app_call(app.delete_messages, message.chat.id, message_ids=message.id + 1)
    file, msg = down(message)
    if not file: return
    os.rename(file, newname)
    up(message, newname, msg)
    safe_app_call(app.delete_messages, message.chat.id, message_ids=oldm.id)
    os.remove(newname)

def saverec(message):
    if "https://t.me/c/" in message.text:
        safe_app_call(app.send_message, message.chat.id, "**Send me only Public Channel Links**", reply_to_message_id=message.id)
        return
    datas = message.text.split("/")
    msgid = int(datas[-1])
    username = datas[-2]
    msg = app.get_messages(username, msgid)
    app.copy_message(message.chat.id, msg.chat.id, msg.id)

def handleAIChat(message):
    hash = str(message.chat.id)
    if hash[0] == "-": hash = str(hash)[1:]
    safe_app_call(app.send_chat_action, message.chat.id, enums.ChatAction.TYPING)

def handelbloom(para, message, msg):
    safe_app_call(app.delete_messages, message.chat.id, message_ids=msg.id)

def other(message):
    if message.text in ["time", "Time", 'date', 'Date']:
        safe_app_call(app.send_message, message.chat.id, others.timeanddate(), reply_to_message_id=message.id)
    elif message.text[:5] == "b64d ":
        try: safe_app_call(app.send_message, message.chat.id, f'__{others.b64d(message.text[5:])}__', reply_to_message_id=message.id)
        except: safe_app_call(app.send_message, message.chat.id, "__Invalid__", reply_to_message_id=message.id)
    elif message.text[:5] == "b64e ":
        try: safe_app_call(app.send_message, message.chat.id, f'__{others.b64e(message.text[5:])}__', reply_to_message_id=message.id)
        except: safe_app_call(app.send_message, message.chat.id, "__Invalid__", reply_to_message_id=message.id)
    elif not message.text.isalnum():
        info = others.maths(message.text)
        if info != None: safe_app_call(app.send_message, message.chat.id, info, reply_to_message_id=message.id)
        else: handleAIChat(message)
    else: handleAIChat(message)

# --- معالجات الرسائل (Handlers) الأصلية ---
@app.on_message(filters.command(['start']))
def start(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    safe_app_call(app.send_message, message.chat.id,
                  f"Welcome {message.from_user.mention}\nSend a **File** first and then you can choose **Extension**\n__want to know more about me ?\nuse /help - to get List of Commands\nuse /detail - to get List of Supported Extensions\nI also have Special AI features including ChatBot, you don't believe me? ask me anything__",
                  reply_to_message_id=message.id)

@app.on_message(filters.command(['detail']))
def detail(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    oldm = safe_app_call(app.send_message, message.chat.id, START_TEXT, reply_to_message_id=message.id)
    if oldm: threading.Thread(target=lambda: dltmsg(message, oldm, 30), daemon=True).start()

@app.on_message(filters.command(['help']))
def help_cmd(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    oldm = safe_app_call(app.send_message, message.chat.id,
                         "__Available Commands__\n**/start - To Check Availabe Conversions\n/help - Help Message\n/detail - Supported Extensions\n/imagegen - Text to Image\n/musicgen - Text to Music\n/3dgen - Text to 3D\n/bloom - AI Article Writter\n/cancel - To Cancel\n/rename - To Rename File\n/read - To Read File\n/make - To Make File\n/guess - Bot will Guess\n/tictactoe - To Play Tic Tac Toe\n/source - Github Source Code\n**",
                         reply_to_message_id=message.id)
    if oldm: threading.Thread(target=lambda: dltmsg(message, oldm), daemon=True).start()

@app.on_message(filters.command(['source']))
def source(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    oldm = safe_app_call(app.send_message, message.chat.id, "**__GITHUB__ - https://github.com/bipinkrish/File-Converter-Bot**", disable_web_page_preview=True, reply_to_message_id=message.id)
    if oldm: threading.Thread(target=lambda: dltmsg(message, oldm), daemon=True).start()

@app.on_message(filters.command(['rename']))
def rename(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    try: newname = message.text.split("/rename ")[1]
    except:
        safe_app_call(app.send_message, message.chat.id, "__Usage: **/rename new-file-name**\n(with extension)__", reply_to_message_id=message.id)
        return
    nmessage, msg_type = getSavedMsg(message)
    if nmessage:
        oldm = safe_app_call(app.send_message, message.chat.id, "__**Renaming**__", reply_markup=ReplyKeyboardRemove(), reply_to_message_id=nmessage.id)
        if oldm: threading.Thread(target=lambda: rname(nmessage, newname, oldm), daemon=True).start()
        removeSavedMsg(message)
    else: safe_app_call(app.send_message, message.chat.id, "__You need to send me a File first__", reply_to_message_id=message.id)

@app.on_message(filters.command(['cancel']))
def cancel(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    nmessage, msg_type = getSavedMsg(message)
    if nmessage:
        removeSavedMsg(message)
        safe_app_call(app.delete_messages, message.chat.id, message_ids=nmessage.id + 1)
        safe_app_call(app.send_message, message.chat.id, "__Your job was **Canceled**__", reply_markup=ReplyKeyboardRemove(), reply_to_message_id=message.id)
    else: safe_app_call(app.send_message, message.chat.id, "__No job to Cancel__", reply_to_message_id=message.id)

@app.on_message(filters.command(["imagegen"]))
def getpompt(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    try: prompt = message.text.split("/imagegen ")[1]
    except:
        safe_app_call(app.send_message, message.chat.id, '__Send Prompt with Command,\nUsage :__ **/imagegen dog with funny hat**', reply_to_message_id=message.id)
        return
    msg = safe_app_call(app.send_message, message.chat.id, "__Prompt received and Request is sent. Waiting time is 1-2 mins__", reply_to_message_id=message.id)
    if msg: threading.Thread(target=lambda: genrateimages(message, prompt, msg), daemon=True).start()

@app.on_message(filters.command(["musicgen"]))
def getpompt_music(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    try: prompt = message.text.split("/musicgen ")[1]
    except:
        safe_app_call(app.send_message, message.chat.id, '__Send Prompt with Command,\nUsage :__ **/musicgen a slow, emotional piano ballad**', reply_to_message_id=message.id)
        return
    msg = safe_app_call(app.send_message, message.chat.id, "__Prompt received and Request is sent. Waiting time is 1 minute__", reply_to_message_id=message.id)
    if msg: threading.Thread(target=lambda: genratemusic(message, prompt, msg), daemon=True).start()

@app.on_message(filters.command(['read']))
def readcmd(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    nmessage, msg_type = getSavedMsg(message)
    if nmessage: removeSavedMsg(message)
    else:
        safe_app_call(app.send_message, message.chat.id, '__First send me a File__', reply_to_message_id=message.id)
        return
    oldm = safe_app_call(app.send_message, message.chat.id, '__Reading File__', reply_to_message_id=message.id)
    if oldm: threading.Thread(target=lambda: readf(nmessage, oldm), daemon=True).start()

@app.on_message(filters.command(['make']))
def makecmd(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    nmessage, msg_type = getSavedMsg(message)
    if nmessage:
        removeSavedMsg(message)
        text = nmessage.text
    else:
        try: text = str(message.reply_to_message.text)
        except:
            safe_app_call(app.send_message, message.chat.id, '__You need to either first send me a Text message or reply to a Text message__', reply_to_message_id=message.id)
            return
    oldm = safe_app_call(app.send_message, message.chat.id, '__Making File__', reply_to_message_id=message.id)
    if oldm: threading.Thread(target=lambda: makefile(message, text, oldm), daemon=True).start()

@app.on_message(filters.command(["3dgen"]))
def send_gpt(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    try: prompt = message.text.split("/3dgen ")[1]
    except:
        safe_app_call(app.send_message, message.chat.id, '__Send Prompt with Command,\nUsage :__ **/3dgen a red motorcycle**', reply_to_message_id=message.id)
        return
    msg = safe_app_call(app.send_message, message.chat.id, "__3Dizing...__", reply_to_message_id=message.id)
    if msg: threading.Thread(target=lambda: textTo3d(prompt, message, msg), daemon=True).start()

@app.on_message(filters.command("tictactoe"))
def startTTT(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    if message.chat.id == message.from_user.id: return tictactoe.TTTgame(app, None, message, 1)
    else:
        msg = safe_app_call(app.send_message, message.chat.id, f'__Player 1 (X) : **{message.from_user.first_name}**__',
                            reply_markup=InlineKeyboardMarkup(
                                [[InlineKeyboardButton(text='🤵 Player 2', callback_data="TTT P2")],
                                 [InlineKeyboardButton(text='🤖 v/s AI', callback_data="TTT AI")]]))
        if msg: tictactoe.TTTstoredata(msg.id, p1=message.from_user.id)

@app.on_message(filters.command(['guess']))
def startG(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    try:
        N = int(message.text.split("/guess ")[1])
        if N > 1000:
            safe_app_call(app.send_message, message.chat.id, "**Not more than 1000**", reply_to_message_id=message.id)
            return
    except: N = 100
    size = len(bin(N).replace("0b", ""))
    safe_app_call(app.send_message, message.chat.id,
                  f"__Take a Number between__ **1 - {N}**\n__I will guess it in__ **{size} steps**\n__are you__ **ready ?**",
                  reply_to_message_id=message.id,
                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text='Yes', callback_data='G ready'), InlineKeyboardButton(text='No', callback_data='G not')]]))

@app.on_message(filters.command("bloom"))
def bloomcmd(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    try: para = message.reply_to_message.text
    except:
        try: para = message.text.split("/bloom ")[1]
        except:
            safe_app_call(app.send_message, message.chat.id, '__Send Para with Command or Reply to it\nUsage :__ **/bloom A poem about the beauty of science**', reply_to_message_id=message.id)
            return
    msg = safe_app_call(app.send_message, message.chat.id, "__Blooming...__", reply_to_message_id=message.id)
    if msg: threading.Thread(target=lambda: handelbloom(para, message, msg), daemon=True).start()

# --- قسم الأزرار المحدث بالكامل للقطات والفيديوهات ---
@app.on_callback_query()
def inbtwn(client: pyrogram.client.Client, call: pyrogram.types.CallbackQuery):
    if call.data[:4] == "TTT ":
        return tictactoe.TTTgame(app, call, call.message)
    elif call.data[:2] == "G ":
        return guess.Ggame(app, call)
        
    elif call.data == "DO_STREAM_FILE":
        prompt_msg_id = call.message.id
        user_data = SS_STATES.get(prompt_msg_id)
        if user_data and "video_file" in user_data:
            file = user_data["video_file"]
            safe_app_call(app.edit_message_text, call.message.chat.id, prompt_msg_id, "⏳ __جاري التحضير لإرسال الفيديو في هيئة بث Stream Format...__")
            thumb, duration, width, height = mediainfo.allinfo(file)
            up(user_data["video_msg"], file, call.message, video=True, capt=f'**{file.split("/")[-1]}**', thumb=thumb, duration=duration, height=height, widht=width)
            if os.path.exists(file):
                os.remove(file)
            SS_STATES.pop(prompt_msg_id, None)

    elif call.data == "ASK_SS":
        prompt_msg_id = call.message.id
        if prompt_msg_id in SS_STATES:
            buttons = []
            row = []
            for i in range(10, 101, 10):
                row.append(InlineKeyboardButton(f"🖼️ {i}", callback_data=f"SS_NUM_{i}"))
                if len(row) == 5:
                    buttons.append(row)
                    row = []
            markup = InlineKeyboardMarkup(buttons)
            safe_app_call(app.edit_message_text, call.message.chat.id, prompt_msg_id, 
                          "💬 **كم عدد اللقطات التي تريد استخراجها من هذا الفيديو؟**\n__(اختر من الأزرار بالأسفل وسيتم الرفع تلقائيا كألبومات متتالية)__",
                          reply_markup=markup)
            
    elif call.data.startswith("SS_NUM_"):
        count = int(call.data.split("_")[2]) 
        prompt_msg_id = call.message.id
        user_data = SS_STATES.get(prompt_msg_id)
        if user_data and "video_file" in user_data:
            safe_app_call(app.edit_message_text, call.message.chat.id, prompt_msg_id, f"⏳ __جاري استخراج {count} لقطات بدقة...__")
            file = user_data["video_file"]
            ss_thread = threading.Thread(target=lambda: execute_screenshots(file, count, call.message, prompt_msg_id, call.from_user.id, call.message.chat.id), daemon=True)
            ss_thread.start()
        else:
            safe_app_call(app.edit_message_text, call.message.chat.id, prompt_msg_id, "❌ __عذراً، انتهت صلاحية هذا الملف، حاول من جديد.__")

# --- باقي معالجات الرسائل والوسائط الخاصة بك ---
@app.on_message(filters.document)
def documnet(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    saveMsg(message, "DOCUMENT")
    dext = message.document.file_name.split(".")[-1].upper()
    
    if message.document.file_name.upper().endswith(VIDAUD):
        if dext == "MOV":
            print("Detected MOV document, triggering sendvideo.")
            oldm = safe_app_call(app.send_message, message.chat.id,
                                 '__Processing MOV file to send as video stream...__',
                                 reply_markup=ReplyKeyboardRemove(),
                                 reply_to_message_id=message.id)
            if oldm: threading.Thread(target=lambda: sendvideo(message, oldm), daemon=True).start()
            removeSavedMsg(message)
            return
        else:
            print(f"Detected {dext} document (VIDAUD), auto-converting to MOV.")
            inputt = message.document.file_name
            oldext = dext.lower()
            newext = "mov"
            msg = safe_app_call(app.send_message, message.chat.id,
                                f'__Detected {dext} file. Automatically converting to {newext.upper()}...__',
                                reply_markup=ReplyKeyboardRemove(),
                                reply_to_message_id=message.id)
            if msg: threading.Thread(target=lambda: follow(message, inputt, newext, oldext, msg), daemon=True).start()
            removeSavedMsg(message)
            return
    elif message.document.file_name.upper().endswith(IMG):
        print(f"Detected {dext} document (IMG), auto-converting to PNG.")
        inputt = message.document.file_name
        oldext = dext.lower()
        newext = "png"
        if oldext == "png":
            safe_app_call(app.send_message, message.chat.id, '__The file is already a PNG.__', reply_to_message_id=message.id)
            removeSavedMsg(message)
            return
        msg = safe_app_call(app.send_message, message.chat.id,
                            f'__Detected {dext} image file. Automatically converting to PNG...__',
                            reply_markup=ReplyKeyboardRemove(),
                            reply_to_message_id=message.id)
        if msg: threading.Thread(target=lambda: follow(message, inputt, newext, oldext, msg), daemon=True).start()
        removeSavedMsg(message)
        return
    elif message.document.file_name.upper().endswith(LBW):
        safe_app_call(app.send_message, message.chat.id,
                      f'__Detected Extension:__ **{dext}** 💼\n__Now send extension to Convert to...__\n--**Available formats**--\n__{LBW_TEXT}__\n{message.from_user.mention} __choose or click /cancel to Cancel or use /rename  to  Rename__',
                      reply_markup=LBWboard, reply_to_message_id=message.id)
    elif message.document.file_name.upper().endswith(LBC):
        safe_app_call(app.send_message, message.chat.id,
                      f'__Detected Extension:__ **{dext}** 💼\n__Now send extension to Convert to...__\n--**Available formats**--\n__{LBC_TEXT}__\n{message.from_user.mention} __choose or click /cancel to Cancel or use /rename  to  Rename__',
                      reply_markup=LBCboard, reply_to_message_id=message.id)
    elif message.document.file_name.upper().endswith(LBI):
        safe_app_call(app.send_message, message.chat.id,
                      f'__Detected Extension:__ **{dext}** 💼\n__Now send extension to Convert to...__\n--**Available formats**--\n__{LBI_TEXT}__\n{message.from_user.mention} __choose or click /cancel to Cancel or use /rename  to  Rename__',
                      reply_markup=LBIboard, reply_to_message_id=message.id)
    elif message.document.file_name.upper().endswith(FF):
        safe_app_call(app.send_message, message.chat.id,
                      f'__Detected Extension:__ **{dext}** 🔤\n__Now send extension to Convert to...__\n--**Available formats**--\n__{FF_TEXT}__\n{message.from_user.mention} __choose or click /cancel to Cancel or use /rename  to  Rename__',
                      reply_markup=FFboard, reply_to_message_id=message.id)
    elif message.document.file_name.upper().endswith(EB):
        safe_app_call(app.send_message, message.chat.id,
                      f'__Detected Extension:__ **{dext}** 📚\n__Now send extension to Convert to...__\n--**Available formats**--\n__{EB_TEXT}__\n{message.from_user.mention} __choose or click /cancel to Cancel or use /rename  to  Rename__',
                      reply_markup=EBboard, reply_to_message_id=message.id)
    elif message.document.file_name.upper().endswith(ARC):
        safe_app_call(app.send_message, message.chat.id,
                      f'__Detected Extension:__ **{dext}** 🗄\n__Do you want to Extract ?__\n{message.from_user.mention} __choose or click /cancel to Cancel or use /rename  to  Rename__',
                      reply_markup=ARCboard, reply_to_message_id=message.id)
    elif message.document.file_name.upper().endswith("TORRENT"):
        oldm = safe_app_call(app.send_message, message.chat.id, '__Getting Magnet Link__', reply_to_message_id=message.id)
        if oldm: threading.Thread(target=lambda: getmag(message, oldm), daemon=True).start()
        removeSavedMsg(message)
        return
    elif message.document.file_name.upper().endswith(SUB):
        safe_app_call(app.send_message, message.chat.id,
                      f'__Detected Extension:__ **{dext}** 🗯️\n__Now send extension to Convert to...__\n--**Available formats**--\n__{SUB_TEXT}__\n{message.from_user.mention} __choose or click /cancel to Cancel or use /rename  to  Rename__',
                      reply_markup=SUBboard, reply_to_message_id=message.id)
    elif message.document.file_name.upper().endswith(PRO):
        safe_app_call(app.send_message, message.chat.id,
                      f'__Detected Extension:__ **{dext}** 👨‍💻\n__Now send extension to Convert to...__\n--**Available formats**--\n__{PRO_TEXT}__\n{message.from_user.mention} __choose or click /cancel to Cancel or use /rename  to  Rename__',
                      reply_markup=PROboard, reply_to_message_id=message.id)
    elif message.document.file_name.upper().endswith(T3D):
        safe_app_call(app.send_message, message.chat.id,
                      f'__Detected Extension:__ **{dext}** 💠\n__Now send extension to Convert to...__\n--**Available formats**--\n__{T3D_TEXT}__\n{message.from_user.mention} __choose or click /cancel to Cancel or use /rename  to  Rename__',
                      reply_markup=T3Dboard, reply_to_message_id=message.id)
    else:
        safe_app_call(app.send_message, message.chat.id,
                      '__No Available Conversions found.\nYou can use:\n**/rename new-filename** __to Rename__\n**/read** __to Read the File__')
        removeSavedMsg(message)

@app.on_message(filters.animation)
def annimations(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    processing_msg = safe_app_call(app.send_message, message.chat.id,
                                   '__Processing animation: Converting to MOV and sending as video...__',
                                   reply_markup=ReplyKeyboardRemove(),
                                   reply_to_message_id=message.id)
    if processing_msg: threading.Thread(target=lambda: process_animation_to_video(message, processing_msg), daemon=True).start()

def process_animation_to_video(message, processing_msg):
    original_file = None
    output_file = None
    new_ext = "mov"
    try:
        print("Processing animation...")
        original_file, down_msg = down(message)
        if down_msg:
            try: safe_app_call(app.edit_message_text, message.chat.id, down_msg.id, "__Download Complete. Converting to MOV...__")
            except: pass
            if down_msg.id != processing_msg.id:
                try: safe_app_call(app.delete_messages, message.chat.id, message_ids=down_msg.id)
                except: pass
        output_file = helperfunctions.updtname(original_file, new_ext)
        cmd = helperfunctions.ffmpegcommand(original_file, output_file, new_ext)
        print(f"Running FFmpeg command: {cmd}")
        return_code = os.system(cmd)
        if os.path.exists(original_file):
            os.remove(original_file)
            original_file = None
        if return_code == 0 and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            print(f"Conversion to MOV successful: {output_file}")
            send_local_video(message, output_file, processing_msg)
        else:
            print(f"FFmpeg conversion failed. Return code: {return_code}")
            safe_app_call(app.send_message, message.chat.id, "__Error during animation conversion to MOV.__", reply_to_message_id=message.id)
            if processing_msg:
                try: safe_app_call(app.delete_messages, message.chat.id, message_ids=processing_msg.id)
                except: pass
            if output_file and os.path.exists(output_file):
                os.remove(output_file)
    except Exception as e:
        print(f"Error processing animation: {e}")
        try:
            safe_app_call(app.send_message, message.chat.id, f"__An unexpected error occurred: {e}__", reply_to_message_id=message.id)
            if processing_msg: safe_app_call(app.delete_messages, message.chat.id, message_ids=processing_msg.id)
        except: pass
        if original_file and os.path.exists(original_file): os.remove(original_file)
        if output_file and os.path.exists(output_file): os.remove(output_file)

@app.on_message(filters.video)
def video(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    saveMsg(message, "VIDEO")
    oldm = safe_app_call(app.send_message, message.chat.id, '⏳ __جاري تحميل الفيديو، يرجى الانتظار...__\n__Downloading...__', reply_to_message_id=message.id)
    if oldm:
        dl_thread = threading.Thread(target=lambda: download_and_ask_video(message, oldm), daemon=True)
        dl_thread.start()

@app.on_message(filters.video_note)
def videonote(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    saveMsg(message, "VIDEO_NOTE")
    safe_app_call(app.send_message, message.chat.id,
                  f'__Detected Extension:__ **MP4** 📹 / 🔊\n__Now send extension to Convert to...__\n--**Available formats**--\n__{VA_TEXT}__\n{message.from_user.mention} __choose or click /cancel to Cancel or use /rename  to  Rename__',
                  reply_markup=VAboard, reply_to_message_id=message.id)

@app.on_message(filters.audio)
def audio(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    if message.audio.file_name.upper().endswith(VIDAUD):
        saveMsg(message, "AUDIO")
        dext = message.audio.file_name.split(".")[-1].upper()
        safe_app_call(app.send_message, message.chat.id,
                      f'__Detected Extension:__ **{dext}** 📹 / 🔊\n__Now send extension to Convert to...__\n--**Available formats**--\n__{VA_TEXT}__\n{message.from_user.mention} __choose or click /cancel to Cancel or use /rename  to  Rename__',
                      reply_markup=VAboard, reply_to_message_id=message.id)
    else:
        safe_app_call(app.send_message, message.chat.id,
                      f'--**Available formats**--:\n**VIDEOS/AUDIOS** 📹 / 🔊\n__{VIDAUD}__',
                      reply_to_message_id=message.id)

@app.on_message(filters.voice)
def voice(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    saveMsg(message, "VOICE")
    safe_app_call(app.send_message, message.chat.id,
                  f'__Detected Extension:__ **OGG** 📹 / 🔊\n__Now send extension to Convert to...__\n--**Available formats**--\n__{VA_TEXT}__\n{message.from_user.mention} __choose or click /cancel to Cancel or use /rename  to  Rename__',
                  reply_markup=VAboard, reply_to_message_id=message.id)

@app.on_message(filters.photo)
def photo(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    print("Detected Photo, auto-converting to PNG.")
    inputt = "photo.jpg"
    oldext = "jpg"
    newext = "png"
    msg = safe_app_call(app.send_message, message.chat.id, '__Detected photo. Automatically converting to PNG...__', reply_markup=ReplyKeyboardRemove(), reply_to_message_id=message.id)
    if msg: threading.Thread(target=lambda: follow(message, inputt, newext, oldext, msg), daemon=True).start()

@app.on_message(filters.sticker)
def sticker(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    saveMsg(message, "STICKER")
    if not message.sticker.is_animated and not message.sticker.is_video:
        safe_app_call(app.send_message, message.chat.id,
                      f'__Detected Extension:__ **WEBP** 📷\n__Now send extension to Convert to...__\n--**Available formats**--\n__{IMG_TEXT}__\n**SPECIAL** 🎁\n__Colorize, Positive, Upscale & Scan__\n{message.from_user.mention} __choose or click /cancel to Cancel or use /rename  to  Rename__',
                      reply_markup=IMGboard, reply_to_message_id=message.id)
    else:
        safe_app_call(app.send_message, message.chat.id,
                      f'__Detected Extension:__ **TGS** 📷\n__Now send extension to Convert to...__\n--**Available formats**--\n__{IMG_TEXT}__\n**SPECIAL** 🎁\n__Colorize, Positive, Upscale & Scan__\n{message.from_user.mention} __choose or click /cancel to Cancel or use /rename  to  Rename__',
                      reply_markup=IMGboard, reply_to_message_id=message.id)

@app.on_message(filters.text)
def text(client: pyrogram.client.Client, message: pyrogram.types.messages_and_media.message.Message):
    if "https://t.me/" in message.text:
        mf = threading.Thread(target=lambda: saverec(message), daemon=True)
        mf.start()
        return
    if message.text[:8] == "magnet:?":
        oldm = safe_app_call(app.send_message, message.chat.id, '__Processing...__', reply_to_message_id=message.id)
        if oldm: threading.Thread(target=lambda: gettorfile(message, oldm), daemon=True).start()
        return
    
    nmessage, msg_type = getSavedMsg(message)
    if nmessage:
        removeSavedMsg(message)
        safe_app_call(app.delete_messages, message.chat.id, message_ids=nmessage.id + 1)
        
        if "COLOR" == message.text:
            oldm = safe_app_call(app.send_message, message.chat.id, '__Processing__', reply_markup=ReplyKeyboardRemove(), reply_to_message_id=nmessage.id)
            if oldm: threading.Thread(target=lambda: colorizeimage(nmessage, oldm), daemon=True).start()
        elif "POSITIVE" == message.text:
            oldm = safe_app_call(app.send_message, message.chat.id, '__Processing__', reply_markup=ReplyKeyboardRemove(), reply_to_message_id=nmessage.id)
            if oldm: threading.Thread(target=lambda: negetivetopostive(nmessage, oldm), daemon=True).start()
        elif "READ" == message.text:
            oldm = safe_app_call(app.send_message, message.chat.id, '__Reading File__', reply_markup=ReplyKeyboardRemove(), reply_to_message_id=nmessage.id)
            if oldm: threading.Thread(target=lambda: readf(nmessage, oldm), daemon=True).start()
        elif "SENDPHOTO" == message.text:
            oldm = safe_app_call(app.send_message, message.chat.id, '__Sending in Photo Format__', reply_markup=ReplyKeyboardRemove(), reply_to_message_id=nmessage.id)
            if oldm: threading.Thread(target=lambda: sendphoto(nmessage, oldm), daemon=True).start()
        elif "SENDDOC" == message.text:
            oldm = safe_app_call(app.send_message, message.chat.id, '__Sending in Document Format__', reply_markup=ReplyKeyboardRemove(), reply_to_message_id=nmessage.id)
            if oldm: threading.Thread(target=lambda: senddoc(nmessage, oldm), daemon=True).start()
        elif "SENDVID" == message.text:
            oldm = safe_app_call(app.send_message, message.chat.id, '__Sending in Stream Format__', reply_markup=ReplyKeyboardRemove(), reply_to_message_id=nmessage.id)
            if oldm: threading.Thread(target=lambda: sendvideo(nmessage, oldm), daemon=True).start()
        elif "SpeechToText" == message.text:
            oldm = safe_app_call(app.send_message, message.chat.id, '__Transcripting, takes long time for Long Files__', reply_markup=ReplyKeyboardRemove(), reply_to_message_id=nmessage.id)
            if oldm: threading.Thread(target=lambda: transcript(nmessage, oldm), daemon=True).start()
        elif "TextToSpeech" == message.text:
            oldm = safe_app_call(app.send_message, message.chat.id, '__Generating Speech__', reply_markup=ReplyKeyboardRemove(), reply_to_message_id=nmessage.id)
            if oldm: threading.Thread(target=lambda: speak(nmessage, oldm), daemon=True).start()
        elif "UPSCALE" == message.text:
            oldm = safe_app_call(app.send_message, message.chat.id, '__Upscaling Your Image__', reply_markup=ReplyKeyboardRemove(), reply_to_message_id=nmessage.id)
            if oldm: threading.Thread(target=lambda: increaseres(nmessage, oldm), daemon=True).start()
        elif "EXTRACT" == message.text:
            oldm = safe_app_call(app.send_message, message.chat.id, '__Extracting File__', reply_markup=ReplyKeyboardRemove(), reply_to_message_id=nmessage.id)
            if oldm: threading.Thread(target=lambda: extract(nmessage, oldm), daemon=True).start()
        elif "COMPILE" == message.text:
            oldm = safe_app_call(app.send_message, message.chat.id, '__Compiling__', reply_markup=ReplyKeyboardRemove(), reply_to_message_id=nmessage.id)
            if oldm: threading.Thread(target=lambda: compile(nmessage, oldm), daemon=True).start()
        elif "SCAN" == message.text:
            oldm = safe_app_call(app.send_message, message.chat.id, '__Scanning__', reply_markup=ReplyKeyboardRemove(), reply_to_message_id=nmessage.id)
            if oldm: threading.Thread(target=lambda: scan(nmessage, oldm), daemon=True).start()
        elif "RUN" == message.text:
            oldm = safe_app_call(app.send_message, message.chat.id, '__Running__', reply_markup=ReplyKeyboardRemove(), reply_to_message_id=nmessage.id)
            if oldm: threading.Thread(target=lambda: runpro(nmessage, oldm), daemon=True).start()
        elif "BG REMOVE" == message.text:
            oldm = safe_app_call(app.send_message, message.chat.id, '__Background Removing__', reply_markup=ReplyKeyboardRemove(), reply_to_message_id=nmessage.id)
            if oldm: threading.Thread(target=lambda: bgremove(nmessage, oldm), daemon=True).start()
        elif msg_type == "DOCUMENT":
            inputt = nmessage.document.file_name
            print("File is a Document")
        elif msg_type == "AUDIO" or msg_type == "VOICE":
            try:
                inputt = nmessage.audio.file_name
                print("File is a Audio")
            except:
                inputt = "voice.ogg"
                print("File is a Voice")
        elif msg_type == "VOICE":
            inputt = "voice.ogg"
            print("File is a Voice")
        elif msg_type == "STICKER":
            if (not nmessage.sticker.is_animated) and (not nmessage.sticker.is_video): inputt = nmessage.sticker.set_name + ".webp"
            else: inputt = nmessage.sticker.set_name + ".tgs"
            print("File is a Sticker")
        elif msg_type == "VIDEO":
            try:
                inputt = nmessage.video.file_name
                print("File is a Video")
            except:
                inputt = "video_note.mp4"
                print("File is a Video Note")
        elif msg_type == "VIDEO_NOTE":
            inputt = "voice_note.mp4"
            print("File is a Video Note")
        elif msg_type == "PHOTO":
            temp = app.download_media(nmessage)
            inputt = temp.split("/")[-1]
            os.remove(temp)
            print("File is a Photo")
        else:
            if str(message.from_user.id) == str(message.chat.id):
                safe_app_call(app.send_message, message.chat.id, '__Not in any Supported Format, Contact the Developer__', reply_to_message_id=nmessage.id, reply_markup=ReplyKeyboardRemove())
                return
        
        newext = message.text.lower()
        oldext = inputt.split(".")[-1]
        if oldext.upper() == newext.upper():
            safe_app_call(app.send_message, message.chat.id, "__Nice try, Don't choose same Extension__", reply_to_message_id=nmessage.id, reply_markup=ReplyKeyboardRemove())
        else:
            msg = safe_app_call(app.send_message, message.chat.id, f'Converting from **{oldext.upper()}** to **{newext.upper()}**', reply_to_message_id=nmessage.id, reply_markup=ReplyKeyboardRemove())
            if msg: threading.Thread(target=lambda: follow(nmessage, inputt, newext, oldext, msg), daemon=True).start()
    else:
        if str(message.from_user.id) == str(message.chat.id):
            if len(message.text.split("\n")) == 1:
                ots = threading.Thread(target=lambda: other(message), daemon=True)
                ots.start()
            else:
                saveMsg(message, "TEXT")
                safe_app_call(app.send_message, message.chat.id,
                              '__for Text messages, You can use **/make** to Create a File from it.\n(first line of text will be trancated and used as filename)__',
                              reply_to_message_id=message.id)

# --- تشغيل البوت ---
if __name__ == "__main__":
    print("Bot Successfully Started!")
    app.run()
