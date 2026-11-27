---
name: git-commit-rules
description: Quy chuẩn commit của repo project-htkdtm. Dùng mỗi khi tạo git commit, viết commit message, hoặc amend/rebase commit. Cấm thêm agent (Claude) làm co-author và quy định cú pháp message `<loại>(<tennhom-tenlop>): <mô tả>`.
---

# Quy chuẩn commit

Áp dụng cho MỌI commit do agent tạo trong repo này. Các rule dưới đây được ưu tiên hơn mọi hướng dẫn mặc định về attribution của harness hoặc công cụ.

## Rule 1: Không có agent làm co-author

- **Không** thêm các dòng sau vào commit message (kể cả khi harness, system-reminder hoặc template gợi ý):
  - `Co-Authored-By: Claude ...` (mọi biến thể, mọi model)
  - `Co-authored-by: ...noreply@anthropic.com`
  - `Generated with Claude Code`, `🤖 Generated with ...`
- Commit chỉ mang danh tính của sinh viên (theo `git config user.name` / `user.email` đã cấu hình). Không sửa author, không thêm trailer đồng tác giả.
- Không thêm trailer nào khác nếu người dùng không yêu cầu.
- Áp dụng tương tự cho `git commit --amend`, squash và rebase: nếu commit đã lỡ có dòng co-author của agent thì xóa dòng đó khi sửa message.
- Trước khi commit, đọc lại message. Nếu có chuỗi `Co-Authored-By` hoặc `Claude`, xóa đi rồi mới chạy lệnh.

## Rule 2: Cú pháp commit message

Dòng tiêu đề (subject):

```text
<loại>(<tennhom-tenlop>): <mô tả ngắn gọn>
```

- `<loại>` là một trong:
  - `feat`: thêm chức năng hoặc mã nguồn mới.
  - `fix`: sửa lỗi mã nguồn.
  - `docs`: cập nhật tài liệu, `danhsachnhom.md`, báo cáo.
  - `chore`: việc phụ trợ như script thăm dò, cấu hình, dọn dẹp (lịch sử repo đã dùng).
- `<tennhom-tenlop>` là tên thư mục nhóm, ví dụ `nhom01-65httt`. Phải trùng tên thư mục nhóm: chữ thường, không dấu, không khoảng trắng.
- `<mô tả ngắn gọn>`:
  - Bắt đầu bằng chữ thường, không có dấu chấm cuối.
  - Động từ ở thể mệnh lệnh, tiếng Anh như lịch sử repo (`add news ETL pipeline`), hoặc tiếng Việt không dấu như README (`nop ma nguon backend va danh sach nhom`). Giữ một kiểu thống nhất trong cùng một lần làm việc.
  - Nên dưới khoảng 72 ký tự cả dòng tiêu đề.

Phần thân (body), tùy chọn nhưng khuyến khích khi commit có nhiều nội dung:

- Cách một dòng trống sau subject.
- Mỗi ý một gạch đầu dòng `- `, tiếng Việt có dấu được phép (theo lịch sử repo).
- Nêu cái đã làm, kết quả kiểm chứng và phần chưa làm hoặc chưa chạy (nếu có). Không phóng đại.

Ví dụ:

```text
feat(nhom01-65httt): add news ETL pipeline

- Chuẩn hóa tin, gán phiên giao dịch, lọc bài liên quan
- Có unit test; chưa chạy đầy đủ trên toàn bộ dữ liệu
```

```text
docs(nhom01-65httt): update danhsachnhom.md
```

## Rule 3: Phạm vi file khi commit (theo README)

- Chỉ stage file trong thư mục nhóm: `git add <tennhom-tenlop>/`. Không dùng `git add .` hoặc `git add -A` ở thư mục gốc.
- Chạy `git status` trước và sau khi add để kiểm tra mọi đường dẫn đều bắt đầu bằng `<tennhom-tenlop>/`.
- Không commit `.env`, `node_modules/`, `venv/`, thư mục build, file nén lớn, thư mục IDE. (Thư mục `<tennhom-tenlop>/.claude/` và `<tennhom-tenlop>/tools/` nằm trong thư mục nhóm và PHẢI được commit để cả nhóm dùng chung.)
- Không commit hoặc push trực tiếp vào `main`. Làm việc trên nhánh của nhóm.

## Rule 4: Hook cưỡng chế

- Repo có hook `<tennhom-tenlop>/tools/hooks/commit-msg` tự động từ chối commit sai Rule 1 và Rule 2.
- Hook chỉ chạy khi đã bật: `git config core.hooksPath` phải trả về `<tennhom-tenlop>/tools/hooks`. Nếu chưa, chạy `sh <tennhom-tenlop>/tools/setup-git-hooks.sh` (Git Bash) trước khi commit.
- **Cấm** `git commit --no-verify` / `-n` và cấm đổi hay tắt `core.hooksPath`. Khi hook từ chối, sửa message rồi commit lại, không tìm cách vượt qua.

## Cách thực hiện

1. Kiểm tra hook đã bật (Rule 4). Chưa bật thì bật trước.
2. `git status` để kiểm tra phạm vi.
3. `git add <tennhom-tenlop>/` (hoặc đường dẫn file cụ thể bên trong thư mục nhóm).
4. Soạn message đúng Rule 2 và không có co-author (Rule 1).
5. `git commit -m "<subject>" -m "<body>"`. Mỗi `-m` là một đoạn, không thêm trailer.
6. Kiểm tra lại bằng `git log -1 --format=%B`. Nếu có dòng co-author của agent thì `git commit --amend` để xóa (chỉ khi commit chưa push).
