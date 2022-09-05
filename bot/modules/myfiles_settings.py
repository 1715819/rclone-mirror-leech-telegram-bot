from pyrogram.types import InlineKeyboardMarkup
from asyncio.subprocess import PIPE, create_subprocess_exec as exec
from json import loads as jsonloads
from bot.helper.ext_utils.message_utils import editMessage, sendMessage
from bot.helper.ext_utils.misc_utils import ButtonMaker, get_rclone_config, get_readable_size


async def settings_myfiles_menu(client, message, msg="", drive_base="", drive_name="", submenu="", 
                                edit=False, is_folder= True,):
    
     if message.reply_to_message:
        user_id= message.reply_to_message.from_user.id
     else:
        user_id= message.from_user.id
     
     buttons= ButtonMaker()

     if submenu == "myfiles_menu_setting":
          if drive_base == "":
               buttons.cbl_buildbutton("📁 Calculate Size", f"myfilesmenu^size_action^{user_id}")
          else:
               if is_folder:
                    buttons.dbuildbutton(f"📁 Calculate Size", f"myfilesmenu^size_action^{user_id}",
                                         f"🗑 Delete", f"myfilesmenu^delete_action^folder^{user_id}")
               else:
                    buttons.cbl_buildbutton ("🗑 Delete", f"myfilesmenu^delete_action^file^{user_id}")
          
          buttons.cbl_buildbutton("✘ Close Menu", f"myfilesmenu^close^{user_id}")

          if edit:
               await editMessage(msg, message, reply_markup= InlineKeyboardMarkup(buttons.first_button))
          else:
               await sendMessage(msg, message, reply_markup= InlineKeyboardMarkup(buttons.first_button))

     elif submenu == "rclone_size":
        path = get_rclone_config(user_id)
        files_count, total_size = await rclone_size(message, drive_base,drive_name, path)
        total_size = get_readable_size(total_size)
        msg= f"Total Files: {files_count}\nFolder Size: {total_size}"
        
        buttons.cbl_buildbutton("✘ Close Menu", f"myfilesmenu^close^{user_id}")

        if edit:
            await editMessage(msg, message, reply_markup= InlineKeyboardMarkup(buttons.first_button))
        else:
            await sendMessage(msg, message, reply_markup= InlineKeyboardMarkup(buttons.first_button))

     elif submenu == "rclone_delete":
          msg= ""
          if is_folder:
               buttons.dbuildbutton("Yes", f"myfilesmenu^yes^folder^{user_id}",
                                    "No", f"myfilesmenu^no^folder^{user_id}")
               msg += f"Are you sure you want to delete this folder permanently?"
          else:
               buttons.dbuildbutton("Yes", f"myfilesmenu^yes^file^{user_id}",
                                    "No", f"myfilesmenu^no^file^{user_id}")
               msg += f"Are you sure you want to delete this file permanently?"

          await editMessage(msg, message, reply_markup= InlineKeyboardMarkup(buttons.first_button))

     elif submenu == "yes":
          msg= ""
          conf_path = get_rclone_config(user_id)
          if is_folder:
               await rclone_purge(message, drive_base, drive_name, conf_path)    
               msg += f"The folder has been deleted successfully!!"
          else:
               await rclone_delete(message, drive_base, drive_name, conf_path)  
               msg += f"The file has been deleted successfully!!"
     
          buttons.cbl_buildbutton("✘ Close Menu", f"myfilesmenu^close^{user_id}")
          
          if edit:
               await editMessage(msg, message, reply_markup= InlineKeyboardMarkup(buttons.first_button))
          else:
               await sendMessage.reply(msg, message, reply_markup= InlineKeyboardMarkup(buttons.first_button)) 

async def rclone_size(message, drive_base, drive_name, conf_path):
     await editMessage("**Calculating Folder Size...**\n\nPlease wait, it will take some time depending on number of files", message)
    
     cmd = ["rclone", "size", f'--config={conf_path}', f"{drive_name}:{drive_base}", "--json"] 
     process = await exec(*cmd, stdout=PIPE, stderr=PIPE)
     stdout, stderr = await process.communicate()
     stdout = stdout.decode().strip()
     return_code = await process.wait()

     if return_code != 0:
          err = stderr.decode().strip()
          return await sendMessage(f'Error: {err}', message)

     data = jsonloads(stdout)
     files = data["count"]
     size = data["bytes"]

     return files, size

async def rclone_purge(message,drive_base, drive_name, conf_path):
     cmd = ["rclone", "purge", f'--config={conf_path}', f"{drive_name}:{drive_base}"] 
     process = await exec(*cmd, stdout=PIPE, stderr=PIPE)
     stdout, stderr = await process.communicate()
     stdout = stdout.decode().strip()
     return_code = await process.wait()

     if return_code != 0:
          err = stderr.decode().strip()
          return await sendMessage(f'Error: {err}', message)

async def rclone_delete(message, drive_base, drive_name, conf_path):
     cmd = ["rclone", "delete", f'--config={conf_path}', f"{drive_name}:{drive_base}"] 
     process = await exec(*cmd, stdout=PIPE, stderr=PIPE)
     stdout, stderr = await process.communicate()
     stdout = stdout.decode().strip()
     return_code = await process.wait()

     if return_code != 0:
          err = stderr.decode().strip()
          return await sendMessage(f'Error: {err}', message)

