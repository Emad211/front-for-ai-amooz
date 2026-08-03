import { ExamPrepV4ExtractionRuntimePanel } from '@/components/teacher/exam-prep-v4/extraction-runtime-panel';
import { ExamPrepV4ReviewPanel } from '@/components/teacher/exam-prep-v4/review-panel';
import { ExamPrepV4SourceMapEditor } from '@/components/teacher/exam-prep-v4/source-map-editor';

export default async function TeacherExamPrepV4SourceMapPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const numericProjectId = Number(projectId);
  return (
    <div className="space-y-6">
      <ExamPrepV4SourceMapEditor projectId={numericProjectId} />
      <ExamPrepV4ExtractionRuntimePanel projectId={numericProjectId} />
      <ExamPrepV4ReviewPanel projectId={numericProjectId} />
    </div>
  );
}
