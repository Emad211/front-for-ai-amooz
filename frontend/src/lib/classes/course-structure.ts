import type { ClassChapter, ClassLesson } from '@/types';

export type CourseStructureRoot = {
  title?: string;
  main_problem?: string;
  target_audience_level?: string;
  estimated_time?: string;
  summary?: string;
  what_you_will_learn?: string[];
};

export type CourseStructureUnit = {
  id?: string;
  title?: string;
  merrill_type?: 'Fact' | 'Concept' | 'Procedure' | 'Principle' | string;
  source_markdown?: string;
  content_markdown?: string;
  teaching_markdown?: string;
  image_ideas?: string[];
};

export type CourseStructureSection = {
  id?: string;
  title?: string;
  units?: CourseStructureUnit[];
};

export type CourseStructure = {
  root_object?: CourseStructureRoot;
  outline?: CourseStructureSection[];
};

export function parseCourseStructure(structureJson: string | undefined | null): CourseStructure | null {
  const raw = (structureJson ?? '').trim();
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object') return null;
    return parsed as CourseStructure;
  } catch {
    return null;
  }
}

export function courseStructureToObjectives(structure: CourseStructure | null): string[] {
  const items = structure?.root_object?.what_you_will_learn;
  if (!Array.isArray(items)) return [];
  return items.map((x) => String(x)).map((x) => x.trim()).filter(Boolean);
}

function toLessonType(_merrillType: CourseStructureUnit['merrill_type']): ClassLesson['type'] {
  // UI currently supports only these types; pick a safe default.
  return 'text';
}

export function courseStructureToChapters(structure: CourseStructure | null, opts?: { isPublished?: boolean }): ClassChapter[] {
  const outline = structure?.outline;
  if (!Array.isArray(outline) || outline.length === 0) return [];

  const isPublished = Boolean(opts?.isPublished);

  return outline.map((section, sectionIndex) => {
    const sectionId = (section?.id || `sec-${sectionIndex + 1}`).toString();
    const units = Array.isArray(section?.units) ? section.units : [];

    return {
      id: sectionId,
      title: (section?.title || `فصل ${sectionIndex + 1}`).toString(),
      order: sectionIndex + 1,
      lessons: units.map((unit, unitIndex) => {
        const unitId = (unit?.id || `${sectionId}-u-${unitIndex + 1}`).toString();
        return {
          id: unitId,
          title: (unit?.title || `درس ${unitIndex + 1}`).toString(),
          type: toLessonType(unit?.merrill_type),
          duration: '—',
          order: unitIndex + 1,
          isPublished,
          contentMarkdown: (unit?.content_markdown || '').toString(),
          teachingMarkdown: (unit?.teaching_markdown || '').toString(),
        };
      }),
    };
  });
}

export function courseStructureToMarkdown(structure: CourseStructure | null): string {
  if (!structure) return '';

  const lines: string[] = [];
  const title = (structure.root_object?.title || '').trim();
  if (title) {
    lines.push(`# ${title}`);
    lines.push('');
  }

  const objectives = courseStructureToObjectives(structure);
  if (objectives.length) {
    lines.push('## اهداف کلاس');
    for (const item of objectives) {
      lines.push(`- ${item}`);
    }
    lines.push('');
  }

  const outline = Array.isArray(structure.outline) ? structure.outline : [];
  outline.forEach((section, sectionIndex) => {
    const sectionTitle = (section?.title || `فصل ${sectionIndex + 1}`).toString().trim();
    lines.push(`## ${sectionIndex + 1}. ${sectionTitle}`);

    const units = Array.isArray(section?.units) ? section.units : [];
    if (!units.length) {
      lines.push('- (بدون زیرسرفصل)');
      lines.push('');
      return;
    }

    units.forEach((unit, unitIndex) => {
      const unitTitle = (unit?.title || `درس ${unitIndex + 1}`).toString().trim();
      lines.push(`- ${sectionIndex + 1}.${unitIndex + 1}. ${unitTitle}`);
    });

    lines.push('');
  });

  return lines.join('\n').trim();
}

export function applyChaptersToCourseStructure(
  original: CourseStructure | null,
  chapters: ClassChapter[]
): CourseStructure {
  const base: CourseStructure = original ? JSON.parse(JSON.stringify(original)) : { root_object: {}, outline: [] };
  const nextOutline: CourseStructureSection[] = chapters.map((chapter, chIndex) => {
    const existingSection = base.outline?.find((s) => String(s.id || '') === String(chapter.id));
    const existingUnits = Array.isArray(existingSection?.units) ? existingSection!.units! : [];

    const nextUnits: CourseStructureUnit[] = chapter.lessons.map((lesson, uIndex) => {
      const existingUnit = existingUnits.find((u) => String(u.id || '') === String(lesson.id));
      return {
        ...(existingUnit ?? {}),
        id: (existingUnit?.id || lesson.id || `u-${uIndex + 1}`).toString(),
        title: lesson.title,
        merrill_type: existingUnit?.merrill_type || 'Concept',
        source_markdown: existingUnit?.source_markdown || '',
        content_markdown: (lesson.contentMarkdown ?? existingUnit?.content_markdown ?? '').toString(),
        teaching_markdown: (lesson.teachingMarkdown ?? existingUnit?.teaching_markdown ?? '').toString(),
        image_ideas: existingUnit?.image_ideas || [],
      };
    });

    return {
      ...(existingSection ?? {}),
      id: (existingSection?.id || chapter.id || `sec-${chIndex + 1}`).toString(),
      title: chapter.title,
      units: nextUnits,
    };
  });

  base.outline = nextOutline;
  return base;
}
