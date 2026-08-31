# MTPDFLogo — Single Source of Truth

สถานะ: Kickoff / v0.1.0

## ขอบเขตที่ยืนยันแล้ว

- Desktop application สำหรับ Windows และ Linux
- Python 3.12 จาก `.venv`
- Source code อยู่ใต้ `app/`
- GUI ใช้ PySide6
- ไม่มี database, SQLAlchemy หรือ Alembic
- ใช้ TOML สำหรับ runtime configuration
- Font bundle อยู่ที่ `app/assets/fonts/`
- ผู้ใช้เพิ่ม Text, Logo หรือทั้งสองชนิดได้หลายรายการ
- แต่ละรายการตั้งค่าแยกกันได้อย่างอิสระ
- ผู้ใช้ต้องวาง Text/Logo ได้ 2 วิธี: เลือกตำแหน่งมาตรฐานจาก dropdown 9 จุด หรือ drag-and-drop วางอิสระบน preview
- ตำแหน่งแบบ drag-and-drop ต้องเก็บเป็น absolute percent ของหน้า (`x_percent`, `y_percent`) ไม่ใช่ screen pixel
- UI ต้องมีทางเลือกที่ชัดเจนสำหรับเพิ่ม Text+Logo พร้อมกันใน workflow เดียว
- ประมวลผลหลาย PDF/รูปภาพแบบแยกไฟล์ ไม่รวม PDF
- รองรับ PDF แนวตั้ง แนวนอน และเอกสารที่มี orientation ผสมกันภายในไฟล์เดียว
- รองรับรูปภาพ `png`, `jpg`, `jpeg` โดยใช้ Text/Logo settings ชุดเดียวกับ PDF
- ผู้ใช้ต้องเลือกไฟล์ได้ทั้งไฟล์เดียวและหลายไฟล์ผ่านปุ่ม `เลือก File(s)` เพียงปุ่มเดียว
- ผู้ใช้ต้องเลือก Input Folder สำหรับ batch ได้จาก toolbar หรือ Batch Queue panel โดยกำหนดได้ว่าจะ recursive หรือไม่ และจำกัดความลึกกี่ชั้น
- การเลือกไฟล์ต้องไม่บังคับเลือก destination folder ในจังหวะเดียวกัน
- ผู้ใช้ตั้งค่า output folder แยกต่างหาก และระบบต้องจำ path ล่าสุดไว้เพื่อความสะดวก
- ผู้ใช้ตั้งค่า output folder ได้ 2 วิธี: กด `เลือก Folder...` หรือวาง path ลง textbox
- ผู้ใช้ต้องบันทึก/โหลดชุด Overlay Settings เป็นไฟล์ TOML ได้
- Batch output ต้องเป็นหนึ่ง output ต่อหนึ่ง input และรักษาโครงสร้าง subfolder ได้เมื่อเลือกใช้
- ในแต่ละไฟล์ประมวลผลทีละหน้าและใช้ parallel ระดับไฟล์
- ผู้ใช้ต้องกำหนดจำนวน workers สำหรับ parallel processing ได้จาก UI
- ต้องรองรับ pytest และ PyInstaller

## Performance baseline

- ไม่ render ทุกหน้าเป็นภาพระหว่าง export
- ใช้ bounded process pool สำหรับ batch
- cache asset ที่ใช้ซ้ำภายในงาน
- ใช้ temporary output และ atomic replace
- มี progress, cancel, resume และ error isolation

## UI/UX and process pipeline

- หน้าจอหลักต้องเป็น workflow เดียวที่อ่านง่าย: เลือกไฟล์/โฟลเดอร์ -> ตั้ง Text/Logo -> ตั้ง Output -> Start Batch -> ตรวจ Output
- ต้องมี pipeline status ที่สะท้อนสถานะจริงของงาน ไม่ใช่ข้อความตกแต่ง
- ปุ่ม `Start Batch` ต้องเริ่มงานเท่านั้น ห้ามประมวลผลอัตโนมัติหลังเลือกไฟล์
- การเลือกไฟล์และการเลือก Output Folder ต้องเป็นคนละ control ชัดเจน
- ปุ่มเลือกไฟล์ต้องมีปุ่มเดียว: `เลือก File(s)`
- Queue table เป็น control หลักของ batch และต้องแสดง input, page count, output, progress, status, error ต่อไฟล์
- Queue table ต้องมีพื้นที่แนวตั้งมากพอสำหรับงานหลายไฟล์ โดย default ต้องสูงกว่าแถบสถานะเล็ก ๆ และผู้ใช้ต้องลาก splitter เพื่อปรับสัดส่วน preview/queue ได้
- Batch Queue ต้องมี controls สำหรับ Input Folder, recursive, depth limit, และ preserve folder structure
- Batch Queue ต้องมี control `Workers` สำหรับจำนวนไฟล์ที่จะประมวลผลพร้อมกัน
- Batch Queue ต้องจัดเป็น Batch Workspace ที่แบ่งกลุ่ม native controls ชัดเจน: Input, Output, Options, Queue
- Batch Workspace ต้องมี summary จำนวนไฟล์และ readiness เพื่อให้ผู้ใช้ไม่ต้องอ่านสถานะจากตารางอย่างเดียว
- ข้อความใน UI ต้องเป็น action-oriented: ชื่อ control ต้องบอกสิ่งที่จะเกิดขึ้นเมื่อผู้ใช้กด
- UI ต้องใช้ OS-native theme เป็นหลัก เพื่อให้หน้าตาเข้ากับ Windows/Linux และลดภาระดูแล custom style
- UI สำหรับงานจำนวนมากต้องเน้น scan ได้เร็ว, spacing สม่ำเสมอ, และสถานะสำคัญต้องมองเห็นทันที
- Layout หลักต้องให้ Preview เป็นพื้นที่ทำงานหลักโดย default เพราะผู้ใช้ต้องตรวจตำแหน่ง/ขนาด/หมุน/opacity จากภาพเอกสารจริง
- Settings ของ Text/Logo ต้องบันทึก/โหลดเป็น preset ได้ เพื่อรองรับ process ซ้ำและลด human error

## Batch contract

- Input: รายการ PDF/รูปภาพหนึ่งไฟล์หรือหลายไฟล์จาก file picker เดียว
- Input Folder: โหลดรายการ PDF/รูปภาพจาก folder ตามค่า recursive/depth ที่ผู้ใช้กำหนด
- Output: `input_name-watermask.ext` ใน output folder ที่เลือก
- เมื่อเปิด `รักษาโครงสร้างโฟลเดอร์ต้นฉบับ` output ต้องคง relative path จาก Input Folder
- ผู้ใช้ต้องสามารถเลือก output folder ปลายทางได้ก่อนเริ่ม Batch
- Output folder จาก textbox ต้องถูก validate ว่ามีอยู่จริงและเป็น folder ก่อน enable `Start Batch`
- การเลือกไฟล์ครั้งใหม่ให้แทนที่ queue เดิม เพื่อให้รายการที่เห็นในตารางคือรายการที่จะประมวลผลจริง
- หลัง export เสร็จ ผู้ใช้ต้องสามารถล้าง queue เดิมและเลือกไฟล์ชุดใหม่เพื่อเริ่มรอบใหม่ได้โดยไม่ต้องปิดโปรแกรม
- หลัง export เสร็จ controls ต้องกลับสู่สถานะพร้อมใช้งานโดยไม่บังคับให้ผู้ใช้เคลียร์ค่าเดิม: ปุ่ม Start ต้องกลับมา enabled เมื่อ queue/output ยัง valid และปุ่ม Cancel ต้อง disabled
- ระบบต้องแสดง output folder ปัจจุบันอย่างชัดเจน และตรวจสอบสิทธิ์เขียน/พื้นที่ว่างก่อนเริ่ม
- ห้าม merge หรือ combine PDF หลายไฟล์
- ไฟล์หนึ่งล้มเหลวต้องไม่หยุดไฟล์อื่นเมื่อ `continue_on_error = true`
- สถานะต้องแยกต่อไฟล์: `pending`, `processing`, `completed`, `failed`, `cancelled`
- ปุ่มหยุด Batch ต้องเป็น safe cancel: หยุดรับงานใหม่/ยกเลิกงานที่ยังไม่เริ่ม, แสดง `Stopping` ระหว่างหยุด, แล้ว mark งานที่ไม่เสร็จเป็น `Cancelled` โดยไม่ทำลาย output ที่เขียนเสร็จแล้ว
- Worker หนึ่งตัวรับผิดชอบ PDF หนึ่งไฟล์ในช่วงเวลาหนึ่ง
- ภายในไฟล์ประมวลผลทีละหน้าแบบ streaming
- Worker หนึ่งตัวรับผิดชอบรูปภาพหนึ่งไฟล์ในช่วงเวลาหนึ่ง และรายงาน progress เป็น 1/1
- จำนวน workers ต้องมาจากค่าที่ผู้ใช้ตั้งใน UI โดยมี default จาก `config/app.toml`

## SSOT rules

1. Requirement และ architectural decisions ที่ขัดแย้งกันให้ยึดไฟล์นี้เป็นหลักจนกว่าจะมีการแก้ไข
2. Runtime defaults อยู่ใน `config/app.toml`
3. Domain rules อยู่ใน `app/mtpdflogo/domain/`
4. UI ห้ามเป็นเจ้าของ business logic
5. ทุก feature ใหม่ต้องมี test ที่เหมาะสม

## Current decisions

- Overlay model คือ `OverlayItem` หนึ่งรายการต่อหนึ่ง Text หรือ Logo
- Overlay preset เป็นไฟล์ TOML มี schema version และเก็บค่าของ Text/Logo แต่ละรายการแยกกัน
- Position ใช้ preset 9 จุด พร้อม offset/margin
- Position mode มี 2 แบบ: `preset` สำหรับ dropdown และ `absolute` สำหรับ drag-and-drop/free position
- Absolute position ใช้ anchor center ใน MVP และต้องคำนวณจากขนาดหน้าจริงของ PDF/Image แต่ละหน้า
- ตำแหน่งต้องคำนวณใหม่จาก `page.rect` ของแต่ละหน้า ห้ามใช้ขนาดหน้าคงที่
- Opacity ใช้ช่วง 0.0–1.0
- Font discovery จะอ่านจาก configured font directory
