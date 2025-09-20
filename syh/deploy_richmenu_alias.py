# syh/deploy_richmenu_alias.py
import os, sys, json, argparse, requests
from PIL import Image

API = "https://api.line.me/v2/bot"
API_DATA = "https://api-data.line.me/v2/bot"

W, H = 2500, 1686
TAB_H = 320  # 上方「選單 A / B / C」可點區塊高度
COL_W = [833, 834, 833]  # 三等分
X_OFF = [0, 833, 1667]

def must_ok(r, msg):
    if not r.ok:
        print(f"[ERROR] {msg}: {r.status_code} {r.text}")
        sys.exit(1)

def check_image(path):
    w, h = Image.open(path).size
    assert (w, h) == (W, H), f"圖片尺寸需 {W}x{H}，現在是 {w}x{h}"

def build_areas():
    # 只做上方三個分區：A、B 用 richmenuswitch；C 先顯示「尚未製作」
    return [
        {"bounds": {"x": X_OFF[0], "y": 0, "width": COL_W[0], "height": TAB_H},
         "action": {"type": "richmenuswitch", "richMenuAliasId": "menu-a", "data": "goto=menuA"}},
        {"bounds": {"x": X_OFF[1], "y": 0, "width": COL_W[1], "height": TAB_H},
         "action": {"type": "richmenuswitch", "richMenuAliasId": "menu-b", "data": "goto=menuB"}},
        {"bounds": {"x": X_OFF[2], "y": 0, "width": COL_W[2], "height": TAB_H},
         "action": {"type": "message", "text": "選單 C（尚未製作）"}},
    ]

def create_menu(token, name, chatbar, areas):
    HJ = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    body = {
        "size": {"width": W, "height": H},
        "selected": False,          # 預設不要自動開（我們等下用 set default 指定）
        "name": name,
        "chatBarText": chatbar,
        "areas": areas
    }
    r = requests.post(f"{API}/richmenu", headers=HJ, data=json.dumps(body).encode("utf-8"))
    must_ok(r, f"create {name}")
    rid = r.json()["richMenuId"]
    print(f"[OK] created {name}: {rid}")
    return rid

def upload_image(token, richmenu_id, image_path):
    HB = {'Authorization': f'Bearer {token}', 'Content-Type': 'image/jpeg'}
    with open(image_path, "rb") as f:
        r = requests.post(f"{API_DATA}/richmenu/{richmenu_id}/content", headers=HB, data=f.read())
    must_ok(r, f"upload image -> {richmenu_id}")
    print(f"[OK] image uploaded -> {richmenu_id}")

def set_default_all(token, richmenu_id):
    H = {'Authorization': f'Bearer {token}'}
    r = requests.post(f"{API}/user/all/richmenu/{richmenu_id}", headers=H)
    must_ok(r, "set default(all)")
    print("[OK] set default(all):", richmenu_id)

def create_or_update_alias(token, alias_id, richmenu_id):
    HJ = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    # 先嘗試建立；存在就改成更新
    r = requests.post(f"{API}/richmenu/alias", headers=HJ,
                      data=json.dumps({"richMenuAliasId": alias_id, "richMenuId": richmenu_id}).encode("utf-8"))
    if r.status_code == 409:  # alias 已存在 → 更新
        r2 = requests.post(f"{API}/richmenu/alias/{alias_id}", headers=HJ,
                           data=json.dumps({"richMenuId": richmenu_id}).encode("utf-8"))
        must_ok(r2, f"update alias {alias_id}")
        print(f"[OK] alias updated: {alias_id} -> {richmenu_id}")
    else:
        must_ok(r, f"create alias {alias_id}")
        print(f"[OK] alias created: {alias_id} -> {richmenu_id}")

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--imageA", default="syh/line/menuA.jpg", help="選單A 背景圖 2500x1686")
    ap.add_argument("--imageB", default="syh/line/menuB.jpg", help="選單B 背景圖 2500x1686")
    ap.add_argument("--chatbar", default="劇團資訊")
    ap.add_argument("--set-default", choices=["menu-a", "menu-b"], default="menu-a")
    ap.add_argument("--delete-others", action="store_true", help="建立後刪除除 A/B 以外的舊選單")
    return ap.parse_args()

def list_menus(token):
    H = {'Authorization': f'Bearer {token}'}
    r = requests.get(f"{API}/richmenu/list", headers=H)
    must_ok(r, "list menus")
    return r.json().get("richmenus", [])

def delete_menu(token, rid):
    H = {'Authorization': f'Bearer {token}'}
    r = requests.delete(f"{API}/richmenu/{rid}", headers=H)
    must_ok(r, f"delete {rid}")
    print("[OK] deleted:", rid)

def main():
    token = os.environ.get("LINE_TOKEN")
    if not token:
        print("請用環境變數 LINE_TOKEN 提供 Channel access token")
        sys.exit(1)

    args = parse_args()
    for p in (args.imageA, args.imageB):
        check_image(p)

    areas = build_areas()

    # 建 A、B 兩張
    rid_a = create_menu(token, "選單A", args.chatbar, areas)
    upload_image(token, rid_a, args.imageA)

    rid_b = create_menu(token, "選單B", args.chatbar, areas)
    upload_image(token, rid_b, args.imageB)

    # 設定 alias
    create_or_update_alias(token, "menu-a", rid_a)
    create_or_update_alias(token, "menu-b", rid_b)

    # 指定全體預設
    set_default_all(token, rid_a if args.__dict__["set_default"] == "menu-a" else rid_b)

    # 刪掉其他非 A/B 的舊選單（可選）
    if args.delete_others:
        keep = {rid_a, rid_b}
        for m in list_menus(token):
            if m["richMenuId"] not in keep:
                delete_menu(token, m["richMenuId"])

    print("\n[完成] 手機版 LINE 開啟和機器人 1:1 聊天 → 點上方『選單 A / 選單 B』即可切換。")

if __name__ == "__main__":
    main()
