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
- ผู้ใช้ต้องเลือกหน้า preview ของ PDF ได้ก่อนวาง Text/Logo เพื่อให้การวางตำแหน่งอ้างอิงหน้าที่ต้องการ ไม่จำกัดหน้าแรก
- Preview ต้องซูมเข้า/ออกและ Fit ได้ โดยการ redraw จากการแก้ Text/Logo ต้องไม่รีเซ็ต zoom
- UI ต้องมีทางเลือกที่ชัดเจนสำหรับเพิ่ม Text+Logo พร้อมกันใน workflow เดียว
- ประมวลผลหลาย PDF/รูปภาพแบบแยกไฟล์ ไม่รวม PDF
- รองรับ PDF แนวตั้ง แนวนอน และเอกสารที่มี orientation ผสมกันภายในไฟล์เดียว
- รองรับรูปภาพ `png`, `jpg`, `jpeg` โดยใช้ Text/Logo settings ชุดเดียวกับ PDF
- ผู้ใช้ต้องเลือกไฟล์ได้ทั้งไฟล์เดียวและหลายไฟล์ผ่านปุ่ม `เลือกไฟล์` เพียงปุ่มเดียว
- ผู้ใช้ต้องเลือก Input Folder สำหรับ batch ได้จาก toolbar หรือ Batch Queue panel โดยกำหนดได้ว่าจะ recursive หรือไม่ และจำกัดความลึกกี่ชั้น
- การเลือกไฟล์ต้องไม่บังคับเลือก destination folder ในจังหวะเดียวกัน
- ผู้ใช้ตั้งค่า output folder แยกต่างหาก และระบบต้องจำ path ล่าสุดไว้เพื่อความสะดวก
- ผู้ใช้ตั้งค่า output folder ได้ 2 วิธี: กด `เลือก Folder...` หรือวาง path ลง textbox
- ผู้ใช้ต้องเลือกได้ว่าจะเปิด output folder อัตโนมัติเมื่อ Batch สำเร็จครบทุกไฟล์หรือไม่ โดย default ต้องปิดไว้และจำค่าเป็น preference
- ผู้ใช้ต้องบันทึก/โหลดชุด Overlay Settings เป็นไฟล์ TOML ได้
- โปรแกรมต้องจำ folder ล่าสุดที่ผู้ใช้ใช้ Save/Load Overlay Settings โดยแยกจาก PDF folder และ output folder
- โปรแกรมต้องมี Recent Settings ล่าสุดสูงสุด 5 รายการ, รองรับการบันทึก/โหลด Default Settings, และเตือนแบบไม่ block หาก preset อ้างถึง logo file ที่ไม่มีอยู่
- ผู้ใช้ต้องเปิด output folder ปลายทางเองได้จากปุ่มข้าง output textbox โดยไม่ต้องรอ Batch สำเร็จ
- Batch output ต้องเป็นหนึ่ง output ต่อหนึ่ง input และรักษาโครงสร้าง subfolder ได้เมื่อเลือกใช้
- ในแต่ละไฟล์ประมวลผลทีละหน้าและใช้ parallel ระดับไฟล์
- ผู้ใช้ต้องกำหนดจำนวน workers สำหรับ parallel processing ได้จาก UI
- ผู้ใช้ต้องกรองหน้า PDF ตามจำนวนคำหรือ regex ที่พบในหน้านั้นได้ โดยนับจาก text layer ของ PDF และ normalize ภาษาไทยก่อนเทียบ
- ผู้ใช้ต้องกรองหน้า PDF ด้วยช่วงหน้าได้ เช่น `1-3,5,10-` โดยใช้ร่วมกับ keyword/regex หรือใช้เฉพาะช่วงหน้าอย่างเดียวได้
- ผู้ใช้ต้องทดสอบ Search/Regex ได้ 2 ระดับ: ไฟล์ preview ปัจจุบัน และ PDF ทั้งหมดใน Queue โดยรูปภาพถูกข้ามเพราะไม่มี text layer
- Regex จากผู้ใช้ต้องมี safe-regex guard เบื้องต้น เช่น จำกัดความยาว pattern และ block nested quantifier ที่เสี่ยงค้าง
- ต้องรองรับ pytest และ zip installer สำหรับ Windows ที่สร้าง `.venv` ด้วย `py -3.12`
- Linux ต้องมี `install.sh` และ `start.sh` สำหรับ source zip โดยใช้ Python 3.12 และ `.venv/bin/python`
- ต้องมี Windows CI บน GitHub Actions สำหรับ lint, pytest coverage gate, runtime import smoke, build zip และ installer smoke
- ต้องมี Linux CI สำหรับ headless lint/test/import smoke และ launcher contract อย่างน้อยก่อน claim cross-OS regression safety

## Performance baseline

- ไม่ render ทุกหน้าเป็นภาพระหว่าง export
- ใช้ bounded process pool สำหรับ batch
- cache asset ที่ใช้ซ้ำภายในงาน
- ใช้ temporary output และ atomic replace
- มี progress, cancel, resume และ error isolation
- Release pipeline ต้องพิสูจน์ clean source zip ว่าไม่มี `.venv`, cache, `.pyc`, `.egg-info`, `build/` หรือ `dist/` ติดไป

## UI/UX and process pipeline

- หน้าจอหลักต้องเป็น workflow เดียวที่อ่านง่าย: เลือกไฟล์/โฟลเดอร์ -> ตั้ง Text/Logo -> ตั้ง Output -> เริ่ม Batch -> ตรวจ Output
- ต้องมี pipeline status ที่สะท้อนสถานะจริงของงาน ไม่ใช่ข้อความตกแต่ง
- ปุ่ม `เริ่ม Batch` ต้องเริ่มงานเท่านั้น ห้ามประมวลผลอัตโนมัติหลังเลือกไฟล์
- การเลือกไฟล์และการเลือก Output Folder ต้องเป็นคนละ control ชัดเจน
- ปุ่มเลือกไฟล์ต้องมีปุ่มเดียว: `เลือกไฟล์`
- Queue table เป็น control หลักของ batch และต้องแสดง input, page count, output, progress, status, error ต่อไฟล์
- Queue table ต้องมีพื้นที่แนวตั้งมากพอสำหรับงานหลายไฟล์ โดย default ต้องสูงอย่างน้อยระดับใช้งานจริง ไม่ถูกบีบจนอ่านไม่ได้ และผู้ใช้ต้องลาก splitter เพื่อปรับสัดส่วน preview/queue ได้
- Queue table ต้องแสดง error ต่อรายการและมีทางให้ผู้ใช้เปิดรายละเอียด error แบบคัดลอกไปส่งต่อ/ตรวจสอบได้
- Batch Queue ต้องมี controls สำหรับ Input Folder, recursive, depth limit, และ preserve folder structure
- Batch Queue ต้องมี control `Workers` สำหรับจำนวนไฟล์ที่จะประมวลผลพร้อมกัน
- Batch Queue ต้องจัดเป็น Batch Workspace แบบ tabs ตามงานผู้ใช้: ไฟล์และปลายทาง, Search/ช่วงหน้า, Processing โดยไม่ซ่อน Queue table
- Batch Workspace tabs หรือ panels ที่มี controls จำนวนมากต้อง scroll ได้เฉพาะภายในพื้นที่นั้น ห้ามทำให้ทั้งหน้าจอ desktop scroll แบบ browser
- Batch Workspace ต้องมี summary จำนวนไฟล์และ readiness เพื่อให้ผู้ใช้ไม่ต้องอ่านสถานะจากตารางอย่างเดียว
- Batch Workspace ต้องมี overall progress bar เพื่อให้ผู้ใช้เห็น progress รวมของ queue โดยไม่ต้องอ่านทีละ row
- ข้อความใน UI ต้องเป็น action-oriented: ชื่อ control ต้องบอกสิ่งที่จะเกิดขึ้นเมื่อผู้ใช้กด
- Empty state ของ Preview/Properties ต้องนำทางผู้ใช้ว่าขั้นตอนแรกควรทำอะไร
- UI ต้องใช้ OS-native theme เป็นหลัก เพื่อให้หน้าตาเข้ากับ Windows/Linux และลดภาระดูแล custom style
- UI ต้องมี `About Dev` เพื่อให้เครดิต `Developer: Masteriii (MT)` โดยไม่ใส่ข้อมูลส่วนตัว/ข้อมูลระบุตัวตนเกินจำเป็น
- UI สำหรับงานจำนวนมากต้องเน้น scan ได้เร็ว, spacing สม่ำเสมอ, และสถานะสำคัญต้องมองเห็นทันที
- Layout หลักต้องให้ Preview เป็นพื้นที่ทำงานหลักโดย default เพราะผู้ใช้ต้องตรวจตำแหน่ง/ขนาด/หมุน/opacity จากภาพเอกสารจริง
- Settings ของ Text/Logo ต้องบันทึก/โหลดเป็น preset ได้ เพื่อรองรับ process ซ้ำและลด human error

## Batch contract

- Input: รายการ PDF/รูปภาพหนึ่งไฟล์หรือหลายไฟล์จาก file picker เดียว
- Input Folder: โหลดรายการ PDF/รูปภาพจาก folder ตามค่า recursive/depth ที่ผู้ใช้กำหนด
- Output: `input_name-watermask.ext` ใน output folder ที่เลือก
- เมื่อเปิด `รักษาโครงสร้างโฟลเดอร์ต้นฉบับ` output ต้องคง relative path จาก Input Folder
- ผู้ใช้ต้องสามารถเลือก output folder ปลายทางได้ก่อนเริ่ม Batch
- Output folder จาก textbox ต้องถูก validate ว่ามีอยู่จริงและเป็น folder ก่อน enable `เริ่ม Batch`
- การเลือกไฟล์ครั้งใหม่ให้แทนที่ queue เดิม เพื่อให้รายการที่เห็นในตารางคือรายการที่จะประมวลผลจริง
- หลัง export เสร็จ ผู้ใช้ต้องสามารถล้าง queue เดิมและเลือกไฟล์ชุดใหม่เพื่อเริ่มรอบใหม่ได้โดยไม่ต้องปิดโปรแกรม
- หลัง export เสร็จ controls ต้องกลับสู่สถานะพร้อมใช้งานโดยไม่บังคับให้ผู้ใช้เคลียร์ค่าเดิม: ปุ่ม Start ต้องกลับมา enabled เมื่อ queue/output ยัง valid และปุ่ม Cancel ต้อง disabled
- ระบบต้องแสดง output folder ปัจจุบันอย่างชัดเจน และตรวจสอบสิทธิ์เขียน/พื้นที่ว่างก่อนเริ่ม
- Output Folder ต้องไม่อยู่ภายใน Input Folder เพื่อป้องกันการประมวลผลไฟล์ output ซ้ำในรอบถัดไป
- ถ้า `overwrite = false` ผู้ใช้ต้องเปิดตัวเลือกเขียนทับอย่างชัดเจนก่อนแทนที่ output เดิม ยกเว้นกรณี resume ที่ manifest ยืนยันว่า output นั้นเสร็จแล้วด้วย settings เดิม
- Batch ต้องมี overlay ที่ทำงานจริงอย่างน้อยหนึ่งรายการก่อนเริ่ม: text ต้องไม่ว่าง และ logo ต้องมีไฟล์ที่มีอยู่จริง
- ห้าม merge หรือ combine PDF หลายไฟล์
- ไฟล์หนึ่งล้มเหลวต้องไม่หยุดไฟล์อื่นเมื่อ `continue_on_error = true`
- สถานะต้องแยกต่อไฟล์: `pending`, `processing`, `completed`, `failed`, `cancelled`
- ปุ่มหยุด Batch ต้องเป็น safe cancel: หยุดรับงานใหม่/ยกเลิกงานที่ยังไม่เริ่ม, แสดง `Stopping` ระหว่างหยุด, แล้ว mark งานที่ไม่เสร็จเป็น `Cancelled` โดยไม่ทำลาย output ที่เขียนเสร็จแล้ว
- การปิดโปรแกรมระหว่าง Batch ต้องไม่ปิดทันทีโดยปล่อย worker เขียนไฟล์ต่อแบบเงียบ ๆ ต้องถามผู้ใช้และสั่ง cancel ก่อน
- Worker หนึ่งตัวรับผิดชอบ PDF หนึ่งไฟล์ในช่วงเวลาหนึ่ง
- ภายในไฟล์ประมวลผลทีละหน้าแบบ streaming
- Worker หนึ่งตัวรับผิดชอบรูปภาพหนึ่งไฟล์ในช่วงเวลาหนึ่ง และรายงาน progress เป็น 1/1
- จำนวน workers ต้องมาจากค่าที่ผู้ใช้ตั้งใน UI โดยมี default จาก `config/app.toml`

## SSOT rules

1. Requirement และ architectural decisions ที่ขัดแย้งกันให้ยึดไฟล์นี้เป็นหลักจนกว่าจะมีการแก้ไข
2. Runtime defaults อยู่ใน `config/app.toml`
3. Domain rules อยู่ใน `app/mtpdflogo/domain/`
4. UI ห้ามเป็นเจ้าของ business logic; export policy/resume/output conflict ต้องอยู่ใน `app/mtpdflogo/application/`
5. ทุก feature ใหม่ต้องมี test ที่เหมาะสม

## Current decisions

- Overlay model คือ `OverlayItem` หนึ่งรายการต่อหนึ่ง Text หรือ Logo
- Overlay preset เป็นไฟล์ TOML มี schema version และเก็บค่าของ Text/Logo แต่ละรายการแยกกัน
- Position ใช้ preset 9 จุด พร้อม offset/margin
- Position mode มี 2 แบบ: `preset` สำหรับ dropdown และ `absolute` สำหรับ drag-and-drop/free position
- Absolute position ใช้ anchor center ใน MVP และต้องคำนวณจากขนาดหน้าจริงของ PDF/Image แต่ละหน้า
- การคลิกเลือก overlay บน preview โดยไม่ได้ลาก ต้องไม่เปลี่ยน `preset` เป็น `absolute`
- ตำแหน่งต้องคำนวณใหม่จาก `page.rect` ของแต่ละหน้า ห้ามใช้ขนาดหน้าคงที่
- PDF/Image logo export ต้องใช้ contract เดียวกัน: resize content ก่อน rotate แล้ว anchor จาก transformed bounds
- Opacity ใช้ช่วง 0.0–1.0
- Font discovery จะอ่านจาก configured font directory
- PDF text export ต้องใช้ renderer ที่รองรับ Thai/Unicode glyphs จาก font ที่เลือกจริง ห้ามปล่อยให้ข้อความไทยกลายเป็น `????`
- Runtime resources เช่น config และ fonts ต้องโหลดได้ทั้ง source tree, editable install, package install, zip installer layout และ PyInstaller `_MEIPASS`
- Export policy ที่ไม่ต้องพึ่ง Qt เช่น settings fingerprint, resume match, output conflict และ output writeability อยู่ใน `app/mtpdflogo/application/export_policy.py`
- Batch readiness และ export preflight ต้องเป็น pure application policy ที่ test ได้โดยไม่ต้อง instantiate `QMainWindow`
- Batch export execution ต้องอยู่ใน `app/mtpdflogo/application/export_engine.py` และ Qt signal adapter อยู่ใน `app/mtpdflogo/presentation/qt_export_worker.py`
- Overlay settings-to-spec mapping ต้องอยู่ใน `app/mtpdflogo/application/overlay_mapper.py`
- Queue/readiness wording ต้องอยู่ใน `app/mtpdflogo/application/queue_state.py`
- Page Search/Regex preview ต้องอยู่ใน `app/mtpdflogo/application/page_search.py`
- Coverage gate เริ่มต้นที่ 75% พร้อม branch coverage และต้องค่อย ๆ ยกระดับเป็น 85%/90% หลังแยก orchestration tests เพิ่ม
- Smoke tests สำหรับ zip installer อยู่ใน `tests/smoke/` และต้องรันด้วย `--run-installer-smoke --no-cov` หลัง build zip
- QA evidence สำหรับ release รอบ 2026-09-05 อยู่ใน `docs/QA_TEST_REPORT_2026-09-05.md`
