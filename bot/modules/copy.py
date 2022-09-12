import configparser
from asyncio.subprocess import PIPE, create_subprocess_exec as exec
from json import loads as jsonloads
from bot import Bot
from pyrogram.filters import regex, command
from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.types import InlineKeyboardMarkup
from os import path as ospath, getcwd
from bot.helper.ext_utils.bot_commands import BotCommands
from bot.helper.ext_utils.filters import CustomFilters
from bot.helper.ext_utils.menu_utils import Menus, rcloneListButtonMaker, rcloneListNextPage
from bot.helper.ext_utils.message_utils import editMessage, sendMarkup, sendMessage
from bot.helper.ext_utils.misc_utils import ButtonMaker, get_rclone_config, pairwise
from bot.helper.ext_utils.rclone_utils import is_not_config
from bot.helper.ext_utils.var_holder import get_rclone_var, set_rclone_var
from bot.helper.mirror_leech_utils.download_utils.rclone.rclone_copy import RcloneCopy

folder_icon= "📁"

async def handle_copy(client, message):
    user_id= message.from_user.id
    if await is_not_config(user_id, message):
        return
    path= ospath.join(getcwd(), "users", str(user_id), "rclone.conf")
    if not ospath.exists(path):
        msg= f"Send an rclone config file, using /config"
        await sendMessage(msg, message)
    else:
        origin_drive = get_rclone_var("COPY_ORIGIN_DRIVE", user_id)      
        origin_dir= get_rclone_var("COPY_ORIGIN_DIR", user_id)
        await list_drive(message, rclone_drive=origin_drive, base_dir=origin_dir, callback="drive_origin")

async def list_drive(message, rclone_drive, base_dir, callback, is_second_menu= False, edit=False):
    if message.reply_to_message:
        user_id= message.reply_to_message.from_user.id
    else:
        user_id= message.from_user.id

    buttons = ButtonMaker()

    path= ospath.join(getcwd(), "users", str(user_id), "rclone.conf")
    conf = configparser.ConfigParser()
    conf.read(path)

    for j in conf.sections():
        if "team_drive" in list(conf[j]):
            buttons.cb_buildsecbutton(f"{folder_icon} {j}", f"copymenu^{callback}^{j}^{user_id}")
        else:
            buttons.cb_buildsecbutton(f"{folder_icon} {j}", f"copymenu^{callback}^{j}^{user_id}")

    for a, b in pairwise(buttons.second_button):
        row= [] 
        if b == None:
            row.append(a)  
            buttons.ap_buildbutton(row)
            break
        row.append(a)
        row.append(b)
        buttons.ap_buildbutton(row)

    buttons.cbl_buildbutton("✘ Close Menu", f"copymenu^close^{user_id}")

    if is_second_menu:
        msg= 'Select folder where you want to copy' 
    else:
        msg= f"Select cloud where your files are stored\n\nPath:`{rclone_drive}:{base_dir}`"     

    if edit:
        await editMessage(msg, message, reply_markup= InlineKeyboardMarkup(buttons.first_button))
    else:
        await sendMarkup(msg, message, reply_markup= InlineKeyboardMarkup(buttons.first_button))

async def list_dir(message, drive_name, drive_base, callback= "", back_callback= "", edit=False, is_second_menu= False):
        user_id= message.reply_to_message.from_user.id
        conf_path = get_rclone_config(user_id)
        buttons = ButtonMaker()

        if is_second_menu:
            buttons.cbl_buildbutton(f"✅ Select this folder", f"copymenu^copy^{user_id}")
            cmd = ["rclone", "lsjson", f'--config={conf_path}', f"{drive_name}:{drive_base}", "--dirs-only"] 
        else:
            buttons.cbl_buildbutton(f"✅ Select this folder", f"copymenu^drive_second^_^False^{user_id}")
            cmd = ["rclone", "lsjson", f'--config={conf_path}', f"{drive_name}:{drive_base}"] 

        process = await exec(*cmd, stdout=PIPE, stderr=PIPE)
        out, err = await process.communicate()
        out = out.decode().strip()
        return_code = await process.wait()

        if return_code != 0:
           err = err.decode().strip()
           return await sendMessage(f'Error: {err}', message)

        list_info = jsonloads(out)
        if is_second_menu:
            list_info.sort(key=lambda x: x["Name"]) 
        else:
            list_info.sort(key=lambda x: x["Size"])  
        set_rclone_var("driveInfo", list_info, user_id)
        
        if len(list_info) == 0:
            buttons.cbl_buildbutton("❌Nothing to show❌", "copymenu^pages^{user_id}")
        else:
            total = len(list_info)
            max_results= 10
            offset= 0
            start = offset
            end = max_results + start
            next_offset = offset + max_results

            if end > total:
                list_info= list_info[offset:]    
            elif offset >= total:
                list_info= []    
            else:
                list_info= list_info[start:end] 
        
            rcloneListButtonMaker(result_list=list_info, 
                buttons= buttons, 
                menu_type = Menus.COPY,
                callback= callback,
                is_second_menu = is_second_menu,
                user_id= user_id)

            if offset == 0 and total <= 10:
                buttons.cbl_buildbutton(f"🗓 {round(int(offset) / 10) + 1} / {round(total / 10)}", "copymenu^pages^{user_id}") 
            else: 
                buttons.dbuildbutton(f"🗓 {round(int(offset) / 10) + 1} / {round(total / 10)}", "copymenu^pages^{user_id}",
                                    "NEXT ⏩", f"next_copy {next_offset} {is_second_menu} {back_callback}")

        buttons.cbl_buildbutton("⬅️ Back", f"copymenu^{back_callback}^{user_id}")
        buttons.cbl_buildbutton("✘ Close Menu", f"copymenu^close^{user_id}")

        if is_second_menu:
            msg=f'Select folder where you want to copy\n\nPath:`{drive_name}:{drive_base}`'
        else:    
            msg= f'Select file or folder which you want to copy\n\nPath: `{drive_name}:{drive_base}`'

        if edit:
            await editMessage(msg, message, reply_markup= InlineKeyboardMarkup(buttons.first_button))
        else:
            await sendMarkup(msg, message, reply_markup= InlineKeyboardMarkup(buttons.first_button))

async def copy_menu_callback(client, callback_query):
    query= callback_query
    data = query.data
    cmd = data.split("^")
    message = query.message
    user_id= query.from_user.id
    origin_drive = get_rclone_var("COPY_ORIGIN_DRIVE", user_id)
    origin_dir= get_rclone_var("COPY_ORIGIN_DIR", user_id)
    dest_drive= get_rclone_var("COPY_DESTINATION_DRIVE", user_id)
    dest_dir= get_rclone_var("COPY_DESTINATION_DIR", user_id)

    if cmd[1] == "pages":
        return await query.answer()

    if int(cmd[-1]) != user_id:
        return await query.answer("This menu is not for you!", alert=True)

    #First Menu
    if cmd[1] == "drive_origin":
        #Clean Menu
        set_rclone_var("COPY_ORIGIN_DIR", "", user_id)
        origin_dir= get_rclone_var("COPY_ORIGIN_DIR", user_id)
        
        origin_drive= cmd[2]
        set_rclone_var("COPY_ORIGIN_DRIVE", origin_drive, user_id)
        await list_dir(message, drive_name= origin_drive, drive_base= origin_dir, callback="origin_dir", edit=True, back_callback= "back_origin")
        await query.answer()

    elif cmd[1] == "origin_dir":
        path = get_rclone_var(cmd[2], user_id)
        origin_dir_= origin_dir + path  + "/"
        set_rclone_var("COPY_ORIGIN_DIR", origin_dir_, user_id)
        await list_dir(message, drive_name= origin_drive, drive_base= origin_dir_, callback="origin_dir", edit=True, back_callback= "back_origin")
        await query.answer()     

    #Second Menu
    elif cmd[1] == "drive_second":
        if cmd[3] == "True":
            path = get_rclone_var(cmd[2], user_id)
            origin_dir_= origin_dir + path  
            set_rclone_var("COPY_ORIGIN_DIR", origin_dir_, user_id)
        await list_drive(message, callback="drive_dest", rclone_drive= dest_drive, base_dir= dest_dir, edit=True, is_second_menu=True)   
        await query.answer()   

    elif cmd[1] == "drive_dest":
        #Clean Menu
        set_rclone_var("COPY_DESTINATION_DIR", "", user_id)
        dest_dir= get_rclone_var("COPY_DESTINATION_DIR", user_id) 

        dest_drive= cmd[2]
        set_rclone_var("COPY_DESTINATION_DRIVE", dest_drive, user_id)
        await list_dir(message, drive_name= dest_drive, drive_base= dest_dir, callback="dir_dest", edit=True, back_callback= "back_dest", is_second_menu=True)
        await query.answer() 

    elif cmd[1] == "dir_dest":
        path = get_rclone_var(cmd[2], user_id)
        dest_dir_= f"{dest_dir}{path}/"
        set_rclone_var("COPY_DESTINATION_DIR", dest_dir_, user_id)
        await list_dir(message, drive_name= dest_drive, drive_base= dest_dir_, callback="dir_dest", edit=True, back_callback= "back_dest", is_second_menu=True)
        await query.answer()     

    elif cmd[1] == "copy":
        await query.answer()      
        rclone_copy= RcloneCopy(message, user_id)
        await rclone_copy.copy()

    elif cmd[1] == "close":
        await query.answer("Closed")
        await message.delete()

    # Origin Menu Back Button
    elif cmd[1] == "back_origin":
        origin_dir_list= origin_dir.split("/")[:-2]
        origin_dir_string = "" 
        for dir in origin_dir_list: 
            origin_dir_string += dir + "/" 
        origin_dir= origin_dir_string
        set_rclone_var("COPY_ORIGIN_DIR", origin_dir, user_id)

        if len(origin_dir) > 0: 
            back_cb= cmd[1]  
            await list_dir(message, drive_name= origin_drive, drive_base= origin_dir, callback="origin_dir", edit=True, back_callback= back_cb, is_second_menu=True)
        else:
            back_cb= "back_origin_menu"
            await list_dir(message, drive_name= origin_drive, drive_base= origin_dir, callback="origin_dir", edit=True, back_callback= back_cb, is_second_menu=True)
        await query.answer()  
        
    elif cmd[1]== "back_origin_menu":
         await list_drive(message, callback="drive_origin", rclone_drive= dest_drive, base_dir= dest_dir, edit=True, is_second_menu=True)        
         await query.answer()   

    # Destination Menu Back Button
    elif cmd[1] == "back_dest":
        dest_dir_list= dest_dir.split("/")[:-2]
        dest_dir_string = "" 
        for dir in dest_dir_list: 
            dest_dir_string += dir + "/"
        dest_dir= dest_dir_string
        set_rclone_var("COPY_DESTINATION_DIR", dest_dir, user_id)
        
        if len(dest_dir) > 0: 
            back_cb= cmd[1]  
            await list_dir(message, drive_name= dest_drive, drive_base= dest_dir, callback="dir_dest", edit=True, back_callback= back_cb, is_second_menu=True)
        else:
            back_cb= "back_dest_menu"
            await list_dir(message, drive_name= dest_drive, drive_base= dest_dir, callback="dir_dest", edit=True, back_callback= back_cb, is_second_menu=True)
        await query.answer() 

    elif cmd[1]== "back_dest_menu":
         await list_drive(message, callback="drive_dest", rclone_drive= dest_drive, base_dir= dest_dir, edit=True, is_second_menu=True)             
         await query.answer() 
        
async def next_page_copy(client, callback_query):
    data= callback_query.data
    message= callback_query.message
    user_id= message.reply_to_message.from_user.id
    _, next_offset, is_second_menu, data_back_cb = data.split()
    is_second_menu = is_second_menu.lower() == 'true'
    list_info = get_rclone_var("driveInfo", user_id)
    total = len(list_info)
    next_offset = int(next_offset)
    prev_offset = next_offset - 10 
    
    buttons = ButtonMaker()
    next_list_info, _next_offset= rcloneListNextPage(list_info, next_offset) 

    if is_second_menu:
        buttons.cbl_buildbutton("✅ Select this folder", f"copymenu^start_copy^{user_id}")
    else:
        buttons.cbl_buildbutton("✅ Select this folder", f"copymenu^rclone_menu_copy^_^False^{user_id}")
    
    if is_second_menu:
        rcloneListButtonMaker(result_list= next_list_info, 
            buttons= buttons,
            menu_type= Menus.COPY,
            callback= "list_dir_dest",
            user_id= user_id,
            is_second_menu= is_second_menu)
    else:
        rcloneListButtonMaker(result_list= next_list_info, 
            buttons= buttons,
            menu_type= Menus.COPY,
            callback= "list_dir_origin",
            user_id= user_id,
            is_second_menu=is_second_menu)

    if next_offset == 0:
        buttons.dbuildbutton(f"🗓 {round(int(next_offset) / 10) + 1} / {round(total / 10)}", "copymenu^pages",
                            "NEXT ⏩", f"next_copy {_next_offset} {is_second_menu} {data_back_cb}")
    
    elif next_offset >= total:
        buttons.dbuildbutton("⏪ BACK", f"next_copy {prev_offset} {is_second_menu} {data_back_cb}",
                            f"🗓 {round(int(next_offset) / 10) + 1} / {round(total / 10)}",
                                   "setting pages")

    elif next_offset + 10 > total:
        buttons.dbuildbutton("⏪ BACK", f"next_copy {prev_offset} {is_second_menu} {data_back_cb}",
                            f"🗓 {round(int(next_offset) / 10) + 1} / {round(total / 10)}","copymenu^pages")                               
    else:
        buttons.tbuildbutton("⏪ BACK", f"next_copy {prev_offset} {is_second_menu} {data_back_cb}",
                            f"🗓 {round(int(next_offset) / 10) + 1} / {round(total / 10)}", "copymenu^pages",
                            "NEXT ⏩", f"next_copy {_next_offset} {is_second_menu} {data_back_cb}")

    buttons.cbl_buildbutton("⬅️ Back", f"copymenu^{data_back_cb}^{user_id}")
    buttons.cbl_buildbutton("✘ Close Menu", f"copymenu^close^{user_id}")
                            
    if is_second_menu:
        dest_drive= get_rclone_var("COPY_DESTINATION_DRIVE", user_id)
        dest_dir= get_rclone_var("COPY_DESTINATION_DIR", user_id)
        await editMessage(f"Select folder where you want to copy\n\nPath:`{dest_drive}:{dest_dir}`", message, 
                        reply_markup= InlineKeyboardMarkup(buttons.first_button))
    else:
        origin_drive= get_rclone_var("COPY_ORIGIN_DRIVE", user_id)
        origin_dir= get_rclone_var("COPY_ORIGIN_DIR", user_id)
        await editMessage(f"Select file or folder which you want to copy\n\nPath:`{origin_drive}:{origin_dir}`", message, 
                        reply_markup= InlineKeyboardMarkup(buttons.first_button))


copy_handler = MessageHandler(handle_copy, filters= command(BotCommands.CopyCommand) & CustomFilters.user_filter | CustomFilters.chat_filter)
next_page_cb= CallbackQueryHandler(next_page_copy, filters= regex("next_copy"))
copy_menu_cb= CallbackQueryHandler(copy_menu_callback, filters= regex("copymenu"))

Bot.add_handler(copy_handler)
Bot.add_handler(next_page_cb)
Bot.add_handler(copy_menu_cb)