import os
import datetime
import time
import traceback
import requests
import re
from playwright.sync_api import (
    Playwright,
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

# <--- IMPORT CONFIG FROM config.py --->
from config import AppConfig

# ==========================================
#  Helper Functions
# ==========================================


def log(msg: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    # ใช้ AppConfig.LOG_FILE
    with open(AppConfig.LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def notify_discord(message: str, success: bool = True):
    # ตรวจสอบจาก AppConfig
    if not AppConfig.DISCORD_WEBHOOK:
        return

    # กำหนดสี: เขียว (สำเร็จ) / แดง (ล้มเหลว)
    color = 0x2ECC71 if success else 0xE74C3C

    payload = {
        "username": "Auto LMS Bot",
        "embeds": [
            {
                "title": "📢 LMS Auto Submit Greenlove",
                "description": message,
                "color": color,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "footer": {
                    "text": "LMS Automation By Playwright",
                },
            }
        ],
    }

    try:
        requests.post(AppConfig.DISCORD_WEBHOOK, json=payload, timeout=10)
    except Exception as e:
        log(f"Discord notify failed: {e}")


def get_thai_date_str():
    now = datetime.datetime.now()
    thai_year = now.year + 543
    return f"{now.day}/{now.month}/{thai_year}"


# ==========================================
#  Main Logic
# ==========================================


def run(playwright: Playwright) -> None:
    print(f"[{datetime.datetime.now()}] เริ่มต้นการทำงาน...")

    # 1. เช็คไฟล์รูปก่อน (Pre-flight Check) โดยใช้ validate ของ Class
    try:
        AppConfig.validate()
    except Exception as e:
        msg = str(e)
        print(msg)
        notify_discord(msg, success=False)
        return

    # คำนวณวันที่และข้อความ
    today_str = get_thai_date_str()
    target_link_name = f"ส่ง Bonus Challenge {today_str}"

    # คำนวณครั้งที่ (ใช้ AppConfig.START_DATE)
    days_diff = (datetime.datetime.now().date() - AppConfig.START_DATE).days + 1
    comment_text = f"ครั้งที่ {days_diff} ลดขยะพลาสติกโดยขวดแก้ว วันที่ {today_str}"

    # เปิด Browser
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:
        # -------------------------------------------------
        # Step 1: Login
        # -------------------------------------------------
        log("Drafting: กำลังล็อกอิน...")
        page.goto("https://lms2.psu.ac.th/login/index.php")
        # ใช้ AppConfig
        page.locator('input[name="username"]').fill(AppConfig.USERNAME)
        page.locator('input[name="password"]').fill(AppConfig.PASSWORD)
        page.locator('button[id="loginbtn"]').click()

        # เช็คว่า Login ผ่านไหม (รอให้ Element หน้า Dashboard โผล่มา)
        try:
            page.wait_for_selector(
                "text=Course overview", state="visible", timeout=30000
            )  # รอ 30 วิ
            log("✅ Login สำเร็จ")
        except PlaywrightTimeoutError:
            log("❌ Login ล้มเหลว (อาจจะรหัสผิด หรือเว็บล่ม)")
            page.screenshot(path="error_login.png")
            notify_discord(
                "❌ **Login ล้มเหลว**\nกรุณาตรวจสอบรหัสผ่านหรือสถานะเว็บ", success=False
            )
            return

        # -------------------------------------------------
        # Step 2: เข้าหน้าวิชา และหาลิงก์วันนี้
        # -------------------------------------------------
        log(f"Drafting: กำลังเข้าสู่หน้าวิชาและหาลิงก์ '{target_link_name}'")
        # ใช้ AppConfig.COURSE_URL
        page.goto(AppConfig.COURSE_URL)

        try:
            # ใช้ exact=False เพื่อหาแบบยืดหยุ่น (เผื่อมีเว้นวรรคเกิน)
            page.get_by_role("link", name=target_link_name, exact=False).click()
            log("✅ เจอลิงก์ส่งงานแล้ว")
        except Exception:
            msg = f"⚠️ Warning: หาลิงก์ '{target_link_name}' ของวันนี้ไม่เจอ\n(อาจารย์อาจจะยังไม่โพสต์ หรือชื่อลิงก์ผิด)"
            log(msg)
            page.screenshot(path="error_link_not_found.png")
            notify_discord(msg, success=False)
            return

        # -------------------------------------------------
        # Step 3: ตรวจสอบสถานะการส่ง (Add vs Edit)
        # -------------------------------------------------
        log("Drafting: ตรวจสอบปุ่มส่งงาน...")

        submission_btn = page.get_by_role("button", name="Add submission")
        edit_btn = page.get_by_role("button", name="Edit submission")

        # รอให้หน้าเว็บโหลดปุ่มเสร็จสมบูรณ์ก่อนเช็ค (Timeout 5 วินาที)
        try:
            # ลองรอปุ่ม Edit ก่อน
            edit_btn.wait_for(state="visible", timeout=3000)
            has_edit = True
        except:
            has_edit = False

        if not has_edit:
            try:
                # ถ้ารอปุ่ม Edit ไม่เจอ ให้ลองรอปุ่ม Add
                submission_btn.wait_for(state="visible", timeout=3000)
                has_add = True
            except:
                has_add = False
        else:
            has_add = False  # ถ้าเจอ Edit แล้ว ก็ถือว่าไม่เจอ Add

        if has_edit:
            log("ℹ️ วันนี้ส่งงานไปแล้ว (พบปุ่ม Edit submission)")
            log("   -> ข้ามการทำงานเพื่อป้องกันการส่งซ้ำ")
            notify_discord(f"ℹ️ **วันนี้ส่งงานไปแล้ว** (Skip)\n{comment_text}", success=True)
            return
        elif has_add:
            log("✅ พบปุ่ม Add submission")
            submission_btn.click()
        else:
            # กรณีหาไม่เจอทั้งคู่ ลองหาแบบ Text ล้วนๆ (ไม้ตายสุดท้าย)
            log("⚠️ ไม่เจอปุ่มแบบปกติ ลองค้นหาด้วยข้อความ...")
            fallback_btn = page.locator("text='Add submission'")
            if fallback_btn.is_visible():
                log("✅ พบปุ่มจากข้อความ (Fallback)")
                fallback_btn.click()
            else:
                log("❌ ไม่จอปุ่มส่งงาน (อาจจะหมดเวลาส่ง หรือ Selector ผิด)")
                page.screenshot(path="error_no_button.png")
                notify_discord(
                    "❌ **ไม่เจอปุ่มส่งงาน** (Add submission)\nอาจจะหมดเวลาส่ง หรือยังไม่เปิด",
                    success=False,
                )
                return

        # -------------------------------------------------
        # Step 4: อัปโหลดไฟล์ (ใช้ AppConfig.IMAGE_FILENAME)
        # -------------------------------------------------
        log(f"Drafting: กำลังอัปโหลดไฟล์ '{AppConfig.IMAGE_FILENAME}'")

        # 1. กดปุ่มไอคอน "Add" (ปุ่มซ้ายบนในกล่อง)
        page.locator(".fp-btn-add").click()

        # 2. ใส่ไฟล์ใน Popup
        page.locator("input[type='file']").set_input_files(AppConfig.IMAGE_FILENAME)

        # 3. กดปุ่ม "Upload this file"
        page.locator("button:has-text('Upload this file')").click()

        # 4. รอให้ "ชื่อไฟล์" ปรากฏขึ้นมา
        file_name = os.path.basename(AppConfig.IMAGE_FILENAME)
        log(f"Drafting: รอตรวจสอบว่าไฟล์ '{file_name}' เข้ามาหรือยัง...")

        page.wait_for_selector(f"text={file_name}", timeout=30000)
        log("✅ อัปโหลดไฟล์เข้า List สำเร็จ")

        # รอ Animation นิ่งๆ สักนิด
        time.sleep(2)

        # 5. กด Save Changes
        log("Drafting: กำลังกดปุ่ม Save changes...")
        page.locator("#id_submitbutton").click(force=True)

        # รอยืนยันการ Save (หน้าจะโหลดใหม่)
        page.wait_for_load_state("networkidle")
        log("✅ บันทึกการส่งงานเรียบร้อย")

        # -------------------------------------------------
        # Step 5: ใส่ Comment
        # -------------------------------------------------
        log("Drafting: กำลังใส่คอมเมนต์...")
        try:
            # หาปุ่ม Comments
            page.locator("a", has_text=re.compile(r"Comments")).click()

            comment_box = page.locator("textarea[rows='2']")
            if not comment_box.is_visible():
                # บางทีต้องกด "Add a comment..." ก่อน
                page.get_by_role("link", name="Add a comment...").click()
                comment_box = page.locator("textarea")

            comment_box.fill(comment_text)
            page.get_by_role("link", name="Save comment").click()
            log(f"✅ คอมเมนต์เรียบร้อย: {comment_text}")

        except Exception as e:
            log(f" ใส่คอมเมนต์ไม่ได้ (แต่ส่งไฟล์แล้ว): {e}")

        log("🎉 เสร็จสิ้นภารกิจประจำวันนี้!")

        # <--- แจ้งเตือนความสำเร็จ (Success) --->
        success_msg = (
            f"✅ **ส่งงานเสร็จสมบูรณ์!**\n"
            f"📅 วันที่: {today_str}\n"
            f"📝 หัวข้อ: {target_link_name}\n"
            f"💬 คอมเมนต์: {comment_text}\n"
            f"📂 ไฟล์: {file_name}"
        )
        notify_discord(success_msg, success=True)

    except Exception as e:
        error_msg = f"**CRITICAL ERROR**\n{e}"
        log(error_msg)
        page.screenshot(
            path=f"error_critical_{datetime.datetime.now().strftime('%H%M%S')}.png"
        )
        notify_discord(error_msg, success=False)

    finally:
        context.close()
        browser.close()


# เรียกใช้งาน
if __name__ == "__main__":
    with sync_playwright() as playwright:
        try:
            log("===== START SCRIPT =====")
            # เพิ่มการ Validate config ก่อนเริ่ม
            AppConfig.validate()
            run(playwright)
            log("===== END SCRIPT (SUCCESS) =====")
        except Exception:
            log("FATAL ERROR")
            log(traceback.format_exc())
