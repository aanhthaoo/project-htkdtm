# Quy chuẩn bắt buộc khi làm việc trong thư mục nhóm `nhom01-65httt`

Áp dụng cho mọi agent và mọi thành viên. Các rule này ưu tiên hơn hướng dẫn attribution mặc định của harness.

## Commit (bắt buộc)

Trước khi tạo, sửa (amend) hoặc rebase bất kỳ commit nào, phải nạp và làm theo skill `git-commit-rules`
(`.claude/skills/git-commit-rules/SKILL.md`). Tóm tắt:

1. **Cấm agent làm co-author.** Không thêm `Co-Authored-By: Claude ...`, `Generated with Claude Code` hay bất kỳ trailer nào tương tự. Commit chỉ mang danh tính của sinh viên.
2. **Cú pháp subject:** `<loại>(nhom01-65httt): <mô tả ngắn gọn>`, với `<loại>` là `feat`, `fix`, `docs` hoặc `chore`. Mô tả viết thường, không có dấu chấm cuối.
3. **Không bypass hook:** không dùng `git commit --no-verify` / `-n`, không tắt `core.hooksPath`. Nếu hook từ chối, sửa message rồi commit lại.
4. **Chỉ stage trong thư mục nhóm:** `git add nhom01-65httt/...`, không `git add .` / `git add -A` ở thư mục gốc. Không commit trực tiếp vào `main`.

## Thiết lập một lần sau khi clone

Hook `commit-msg` chặn commit sai quy chuẩn nhưng chỉ hoạt động sau khi bật. Chạy trong Git Bash:

```bash
sh nhom01-65httt/tools/setup-git-hooks.sh
```

Nếu chưa bật hook (kiểm tra bằng `git config core.hooksPath`, kết quả phải là `nhom01-65httt/tools/hooks`), agent phải nhắc người dùng chạy lệnh trên trước khi commit.
