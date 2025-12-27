export interface Course {
  id: number;
  title: string;
  description: string;
  tags: string[];
}

export interface Exam {
  id: number;
  title: string;
  description: string;
  tags: string[];
  questions: number;
}

export interface Activity {
  title: string;
  time: string;
  type: string;
  icon: React.ReactNode;
}

export interface Event {
  title: string;
  status: string;
  date: string;
  month: string;
  icon: React.ReactNode;
}

export interface Student {
  id: string;
  name: string;
  email: string;
  phone: string;
  avatar: string;
  enrolledClasses: number;
  completedLessons: number;
  totalLessons: number;
  averageScore: number;
  status: 'active' | 'inactive';
  joinDate: string;
  lastActivity: string;
  performance: 'excellent' | 'good' | 'needs-improvement';
}

export interface NavItem {
  label: string;
  href: string;
  icon?: any;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}
