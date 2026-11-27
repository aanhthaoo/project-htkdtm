// Vai trò: guest < investor < admin (khớp backend)
export const ROLE_RANK = { guest: 0, investor: 1, admin: 2 };
export const ROLE_LABEL = { guest: "Khách", investor: "Nhà đầu tư", admin: "Quản trị" };

export function hasRole(user, minRole) {
  const rank = user ? ROLE_RANK[user.role] : ROLE_RANK.guest;
  return rank >= ROLE_RANK[minRole];
}
