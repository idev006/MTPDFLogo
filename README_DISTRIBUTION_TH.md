# MTPDFLogo — วิธีติดตั้งและใช้งาน

## สำหรับผู้ใช้ทั่วไปบน Windows

1. แตกไฟล์ zip ไปไว้ในโฟลเดอร์ที่ต้องการ
2. ดับเบิลคลิก `install.bat` หนึ่งครั้ง
3. เมื่อติดตั้งเสร็จ ดับเบิลคลิก `start.bat` เพื่อเปิดโปรแกรม

ถ้าโปรแกรมไม่เปิด หรืออยากเห็นข้อความ error ให้ดับเบิลคลิก `start-debug.bat`
แทน `start.bat` หน้าต่างนี้จะค้างไว้เพื่อแสดง traceback/error ให้ตรวจสอบได้ง่าย

## สำหรับผู้ใช้ Linux

1. แตกไฟล์ zip ไปไว้ในโฟลเดอร์ที่ต้องการ
2. เปิด Terminal ในโฟลเดอร์นั้น
3. รัน `sh install.sh` หนึ่งครั้ง
4. เมื่อติดตั้งเสร็จ รัน `sh start.sh`

ถ้าเครื่องใช้คำสั่ง Python 3.12 ชื่ออื่น สามารถระบุเองได้ เช่น:

```sh
PYTHON_BIN=/usr/bin/python3.12 sh install.sh
```

## สิ่งที่ต้องมีในเครื่อง

- Windows: Python 3.12 และใช้คำสั่ง `py -3.12` ได้จาก Command Prompt
- Linux: Python 3.12 และ module `venv`
- Internet สำหรับติดตั้ง dependencies ครั้งแรก
- package นี้เป็น source zip installer ไม่ใช่ standalone `.exe`

## การใช้งานหลัก

- กด `เลือกไฟล์` เพื่อเลือก PDF หรือรูปภาพหนึ่งไฟล์/หลายไฟล์
- ตั้งค่า Text/Logo ทางซ้ายและขวา
- ถ้าเป็น PDF หลายหน้า สามารถเลือกหน้า Preview ที่ต้องการก่อนลากวาง Text/Logo ได้
- ใช้ปุ่ม `-`, `Fit`, `+` หรือ `Ctrl + mouse wheel` เพื่อซูม Preview
- ตั้ง Output Folder แยกต่างหาก
- กด `เริ่ม Batch` เพื่อเริ่มประมวลผล
- โปรแกรมจะตั้งชื่อ output อัตโนมัติเป็น `ชื่อไฟล์เดิม-watermask.ext`
- ถ้าต้องการทำเฉพาะบางหน้า PDF ให้ติ๊ก `วางเฉพาะหน้าที่พบคำนี้` แล้วใส่คำหรือ regex พร้อมช่วงจำนวนครั้งต่อหน้า
- ถ้า output เดิมมีอยู่ ต้องติ๊ก `เขียนทับ output เดิม` ก่อน โปรแกรมจึงจะแทนที่ไฟล์เดิม

## สำหรับผู้พัฒนา / การ Build

ก่อนส่งมอบ build ให้รัน:

```bat
build.bat
```

คำสั่งนี้จะรัน `ruff`, `pytest` แล้วสร้างไฟล์ `dist\MTPDFLogo-installer.zip`
ภายใน zip จะมี `install.bat` สำหรับ Windows และ `install.sh` สำหรับ Linux เพื่อสร้าง `.venv`
และติดตั้ง dependencies
`pytest` จะวัด coverage และต้องผ่านขั้นต่ำ 75%

ถ้าต้องการทดสอบ installer zip แบบเครื่องสะอาด ให้รันหลัง `build.bat`:

```bat
.venv\Scripts\python.exe -m pytest tests\smoke -q --no-cov --run-installer-smoke --installer-zip dist\MTPDFLogo-installer.zip
```

## หมายเหตุ

- โปรแกรมไม่รวมไฟล์ PDF หลายไฟล์เข้าด้วยกัน
- หนึ่ง input จะได้หนึ่ง output
- ถ้ากดหยุด Batch โปรแกรมจะหยุดอย่างปลอดภัย โดยรอไฟล์ที่กำลังทำอยู่จบก่อน
- ไม่ควรตั้ง Output Folder ไว้ภายใน Input Folder เพราะโปรแกรมจะป้องกันเพื่อไม่ให้ไฟล์ output ถูกนำกลับมาประมวลผลซ้ำ
