# Feature: Free Position Drag & Drop

สถานะ: Planned -> Implementing  
Branch: `feature/free-position-drag-drop`

## Goal

เพิ่มการวาง Text/Logo แบบอิสระบน preview ด้วย drag-and-drop โดยยังคง dropdown 9 ตำแหน่งเดิมไว้ครบ

## Team viewpoints

### Sr. Software / Process Engineer

- `main` ต้องเป็น stable branch
- feature ใหม่ต้องอยู่บน branch แยก
- Preview, PDF export และ image export ต้องใช้ coordinate contract เดียวกัน
- Save/load settings ต้องรองรับทั้ง preset และ absolute
- ต้องมี regression tests ก่อน merge

### Sr. Python Engineer

- ตำแหน่ง absolute ต้องเก็บเป็น percent ของหน้า ไม่ใช่ screen pixel
- UI event จากการลากต้องอัปเดตเฉพาะ overlay item ที่ selected/ถูกลาก
- หลีกเลี่ยง business logic ฝังใน widget ให้มากที่สุด
- ใช้ pure function สำหรับ position resolving เพื่อ test ได้

### Sr. UI/UX Designer

- ผู้ใช้ต้องรู้ทันทีว่ารายการกำลังใช้ `ตำแหน่งมาตรฐาน` หรือ `วางอิสระ`
- การลากบน preview ต้องเปลี่ยนเป็น absolute mode อัตโนมัติ
- Dropdown เดิมยังต้องใช้ง่ายสำหรับผู้ใช้ทั่วไป
- X/Y controls เป็นตัวช่วย fine tune ไม่ใช่ภาระหลัก
- ต้องมีทางกลับไปใช้ dropdown: `กลับไปใช้ตำแหน่งมาตรฐาน`

## Position contract

### Preset mode

```text
position_mode = "preset"
position = "middle_center"
```

ใช้ dropdown 9 ตำแหน่งเดิม

### Absolute mode

```text
position_mode = "absolute"
x_percent = 50.0
y_percent = 25.0
anchor = "center"
```

`x_percent` และ `y_percent` คือจุดกึ่งกลางของ overlay เทียบกับขนาดหน้า

```text
x = page_width  * x_percent / 100
y = page_height * y_percent / 100
```

ตำแหน่ง top-left สำหรับวาด:

```text
left = x - overlay_width / 2
top  = y - overlay_height / 2
```

## UI flow

```text
User selects overlay item
  |
  v
Properties > Layout shows:
  - dropdown position
  - position mode
  - X (%)
  - Y (%)
  - reset to preset button
```

## Sequence: drag item

```text
User drags selected Text/Logo on Preview
  |
  v
Draggable graphics item moves in scene
  |
  v
Mouse release
  |
  v
MainWindow maps item center to page percent
  |
  v
Overlay model:
  position_mode = absolute
  x_percent/y_percent updated
  |
  v
Properties controls update
  |
  v
Preview redraws from model
```

## Sequence: dropdown position

```text
User changes dropdown position
  |
  v
Overlay model:
  position_mode = preset
  position = selected preset
  |
  v
Preview/export resolve from preset
```

## Sequence: export

```text
Batch job
  |
  v
PDF/Image processor
  |
  v
resolve_overlay_position()
  |
  +-- preset mode -> 9-point anchor
  |
  +-- absolute mode -> percent coordinate
  |
  v
Draw Text/Logo
```

## MVP scope

- Drag Text/Logo ได้
- เก็บ X/Y เป็น percent
- PDF export ใช้ absolute ได้
- Image export ใช้ absolute ได้
- Save/load TOML รองรับ absolute
- Dropdown เดิมยังใช้ได้

## Later scope

- Arrow-key nudge
- Snap guides
- Lock item
- Duplicate item
- Resize/rotate handles on preview
