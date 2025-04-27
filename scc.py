#coding=utf-8
#coding=gbk
# @author: rourou
# @file: scc.py.py
# @time: 2025/4/27 15:17
# @desc:
import sys

from pymongo.errors import PyMongoError

from sc import MongoDBManager


# ...（前面的代码保持不变）

def main():
    if len(sys.argv) != 2:
        print("用法: python scc.py <UID>")
        return

    uid = int(sys.argv[1])
    manager = MongoDBManager()

    if not manager.connect():
        print("无法连接到 MongoDB")
        return

    try:
        print(f"查询 UID: {uid} 的玩家数据:")
        manager.get_racetrack_data(uid)

        # 示例更新
        print(f"\n更新 UID: {uid} 的玩家数据:")
        new_score = 2000
        new_level = 15
        manager.update_racetrack_data(uid, new_score, new_level)

    except PyMongoError as e:
        print(f"操作失败: {e}")
    finally:
        manager.close()
        print("数据库连接已关闭")


if __name__ == "__main__":
    main()