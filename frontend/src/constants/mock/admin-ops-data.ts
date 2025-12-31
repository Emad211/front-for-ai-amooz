export const MOCK_SERVER_HEALTH = {
  status: 'healthy' as const,
  uptime: '42 روز',
  cpu: 41,
  memory: 63,
  disk: 58,
  incidentsThisMonth: 0,
  lastIncident: '۱۴۰۳/۰۴/۱۲',
};

export const MOCK_MAINTENANCE_TASKS = [
  {
    id: 'm1',
    title: 'به‌روزرسانی سیستم‌عامل سرور اصلی',
    window: 'پنجشنبه ۲۳:۳۰ - ۰۱:۳۰',
    owner: 'DevOps',
    status: 'scheduled' as const,
  },
  {
    id: 'm2',
    title: 'پاکسازی لاگ‌ها و کش قدیمی',
    window: 'جمعه ۰۲:۰۰ - ۰۳:۰۰',
    owner: 'SRE',
    status: 'scheduled' as const,
  },
  {
    id: 'm3',
    title: 'تست بازیابی از بک‌آپ',
    window: 'شنبه ۰۶:۰۰ - ۰۷:۰۰',
    owner: 'SRE',
    status: 'ready' as const,
  },
];

const recentDate = (offsetDays: number) => {
  const d = new Date();
  d.setDate(d.getDate() - offsetDays);
  return d.toLocaleDateString('fa-IR');
};

export const MOCK_BACKUPS = Array.from({ length: 6 }).map((_, idx) => ({
  id: `b${idx + 1}`,
  createdAt: recentDate((idx + 1) * 3),
  size: `${12 + idx * 2} GB`,
  type: idx % 3 === 0 ? 'full' : 'incremental',
  status: 'completed' as const,
}));

export const MOCK_SERVER_SETTINGS = {
  autoBackup: true,
  backupWindow: '۰۳:۰۰ - ۰۴:۰۰',
  backupRetentionDays: 14,
  maintenanceAutoApprove: false,
  alertEmail: 'ops@example.com',
};
