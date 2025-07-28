import os
import re
import shutil

def increment_file_numbers_safe(directory, increment_value, destination_directory):
    try:
        print("正在读取目录...")
        files = os.listdir(directory)
        files.sort()
        print(f"找到文件: {files}")

        temp_rename_map = {}  # 原始 -> 临时
        final_rename_map = {}  # 临时 -> 最终

        temp_suffix = "__TEMP__"  # 用于临时命名，避免重名

        # 创建目标文件夹（如不存在）
        if not os.path.exists(destination_directory):
            os.makedirs(destination_directory)
            print(f"📁 已创建目标文件夹: {destination_directory}")

        # 第一步：生成临时文件名（加很大的号）
        for file in files:
            file_path = os.path.join(directory, file)
            if os.path.isfile(file_path):
                match = re.search(r"(.*?)(\d+)(\.\w+)?$", file)
                if match:
                    prefix = match.group(1)
                    number = int(match.group(2))
                    extension = match.group(3) if match.group(3) else ""

                    temp_number = number + 10000  # 临时大号
                    temp_name = f"{prefix}{temp_number:05d}{temp_suffix}{extension}"
                    temp_path = os.path.join(directory, temp_name)

                    new_number = number + increment_value
                    final_name = f"{prefix}{new_number:02d}{extension}"
                    final_path = os.path.join(directory, final_name)

                    temp_rename_map[file_path] = temp_path
                    final_rename_map[temp_path] = final_path
                else:
                    print(f"跳过未匹配文件: {file}")

        # 第二步：先重命名为临时名，避免冲突
        for old_path, temp_path in temp_rename_map.items():
            os.rename(old_path, temp_path)
            print(f"临时重命名: {os.path.basename(old_path)} -> {os.path.basename(temp_path)}")

        # 第三步：再重命名为最终名
        for temp_path, final_path in final_rename_map.items():
            os.rename(temp_path, final_path)
            print(f"最终重命名: {os.path.basename(temp_path)} -> {os.path.basename(final_path)}")

        # 第四步：剪切最终文件到目标文件夹
        for _, final_path in final_rename_map.items():
            filename = os.path.basename(final_path)
            dest_path = os.path.join(destination_directory, filename)
            shutil.move(final_path, dest_path)
            print(f"📦 已移动文件: {filename} -> {destination_directory}")

        print("✅ 文件重命名并移动完成。")

    except Exception as e:
        print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    # 修改为你的源路径和目标路径
    target_directory = r"D:\video\2025.0709\2025.070903_1"
    destination_directory = r"D:\video\2025.0716\2025.0716spot1_1"
    increment = 70  # 比如把 frame_05.jpg 变成 frame_19.jpg
    increment_file_numbers_safe(target_directory, increment, destination_directory)
