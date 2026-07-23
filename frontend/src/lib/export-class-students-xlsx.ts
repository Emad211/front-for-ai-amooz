import type { ClassStudent } from '@/types';
import { formatPersianDate, formatPersianDateTime } from '@/lib/date-utils';

const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

function safeFileName(value: string): string {
  return value.replace(/[<>:"/\\|?*\u0000-\u001f]/g, '-').trim() || 'students';
}

export async function exportClassStudentsXlsx(title: string, students: ClassStudent[]): Promise<void> {
  if (!students.length) {
    throw new Error('دانش‌آموزی برای خروجی گرفتن وجود ندارد.');
  }

  const ExcelJS = await import('exceljs');
  const workbook = new ExcelJS.Workbook();
  workbook.creator = 'AI-Amooz';
  const sheet = workbook.addWorksheet('دانش‌آموزان', {
    views: [{ rightToLeft: true, state: 'frozen', ySplit: 1 }],
  });

  sheet.columns = [
    { header: 'نام دانش‌آموز', key: 'name', width: 26 },
    { header: 'شماره موبایل', key: 'phone', width: 18 },
    { header: 'ایمیل', key: 'email', width: 30 },
    { header: 'کد دعوت', key: 'inviteCode', width: 22 },
    { header: 'پیشرفت', key: 'progress', width: 14 },
    { header: 'وضعیت', key: 'status', width: 14 },
    { header: 'تاریخ عضویت', key: 'joinDate', width: 20 },
    { header: 'آخرین فعالیت', key: 'lastActivity', width: 20 },
  ];

  students.forEach((student) => {
    sheet.addRow({
      name: student.name,
      phone: student.phone || '',
      email: student.email || '',
      inviteCode: student.inviteCode || '',
      progress: student.progress / 100,
      status: student.status === 'active' ? 'فعال' : 'غیرفعال',
      joinDate: formatPersianDate(student.joinDate),
      lastActivity: student.lastActivity ? formatPersianDateTime(student.lastActivity) : '-',
    });
  });

  sheet.getRow(1).font = { bold: true };
  sheet.getColumn('progress').numFmt = '0%';
  sheet.autoFilter = { from: 'A1', to: 'H1' };

  const buffer = await workbook.xlsx.writeBuffer();
  const url = URL.createObjectURL(new Blob([buffer], { type: XLSX_MIME }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `${safeFileName(title)}-${safeFileName(formatPersianDate(new Date()))}.xlsx`;
  link.click();
  URL.revokeObjectURL(url);
}
