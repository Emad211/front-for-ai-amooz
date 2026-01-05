'use client';

import { MarkdownWithMath } from '@/components/content/markdown-with-math';
import { parseCourseStructure, courseStructureToObjectives, type CourseStructure } from '@/lib/classes/course-structure';

type StructuredContentViewProps = {
  structureJson: string;
};

function safeStructure(structureJson: string): CourseStructure | null {
  return parseCourseStructure(structureJson);
}

export function StructuredContentView({ structureJson }: StructuredContentViewProps) {
  const structure = safeStructure(structureJson);
  const objectives = courseStructureToObjectives(structure);
  const outline = Array.isArray(structure?.outline) ? structure!.outline! : [];

  if (!structure) {
    return <div className="text-xs text-muted-foreground">هنوز ساختار مرحله ۲ آماده نیست.</div>;
  }

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <div className="text-sm font-bold">اهداف یادگیری</div>
        {objectives.length ? (
          <ul className="list-disc pr-6 space-y-1 text-sm">
            {objectives.map((obj, i) => (
              <li key={`${i}-${obj}`}>{obj}</li>
            ))}
          </ul>
        ) : (
          <div className="text-xs text-muted-foreground">—</div>
        )}
      </div>

      <div className="space-y-2">
        <div className="text-sm font-bold">فهرست مطالب</div>
        {outline.length ? (
          <ol className="list-decimal pr-6 space-y-1 text-sm">
            {outline.map((section, sectionIndex) => {
              const units = Array.isArray(section?.units) ? section.units : [];
              return (
                <li key={String(section?.id || sectionIndex)} className="space-y-1">
                  <div>{String(section?.title || `فصل ${sectionIndex + 1}`)}</div>
                  {units.length ? (
                    <ol className="list-decimal pr-6 space-y-1 text-sm">
                      {units.map((unit, unitIndex) => (
                        <li key={String(unit?.id || unitIndex)}>{String(unit?.title || `درس ${unitIndex + 1}`)}</li>
                      ))}
                    </ol>
                  ) : (
                    <div className="text-xs text-muted-foreground">(بدون زیرسرفصل)</div>
                  )}
                </li>
              );
            })}
          </ol>
        ) : (
          <div className="text-xs text-muted-foreground">—</div>
        )}
      </div>

      <div className="space-y-3">
        <div className="text-sm font-bold">متن فصل‌ها و زیرسرفصل‌ها</div>
        {outline.length ? (
          <div className="space-y-6">
            {outline.map((section, sectionIndex) => {
              const sectionTitle = String(section?.title || `فصل ${sectionIndex + 1}`);
              const units = Array.isArray(section?.units) ? section.units : [];

              return (
                <div key={String(section?.id || sectionIndex)} className="space-y-3">
                  <div className="text-base font-black">{sectionIndex + 1}. {sectionTitle}</div>

                  {units.length ? (
                    <div className="space-y-4">
                      {units.map((unit, unitIndex) => {
                        const unitTitle = String(unit?.title || `درس ${unitIndex + 1}`);
                        const content = String(unit?.content_markdown || '').trim();
                        const teaching = String(unit?.teaching_markdown || '').trim();
                        const combined = [
                          content ? `# ${unitTitle}\n\n${content}` : `# ${unitTitle}\n\n(متن این زیرسرفصل هنوز ثبت نشده است.)`,
                          teaching ? `\n\n## راهنمای تدریس\n\n${teaching}` : '',
                        ].join('');

                        return (
                          <div key={String(unit?.id || unitIndex)} className="rounded-2xl border border-border/60 bg-background/80 p-4">
                            <MarkdownWithMath markdown={combined} className="space-y-2" />
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="text-xs text-muted-foreground">(بدون زیرسرفصل)</div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-xs text-muted-foreground">—</div>
        )}
      </div>
    </div>
  );
}
