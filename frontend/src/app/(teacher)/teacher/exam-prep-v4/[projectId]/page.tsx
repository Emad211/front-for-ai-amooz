import { ExamPrepV4SourceMapEditor } from '@/components/teacher/exam-prep-v4/source-map-editor';

export default async function TeacherExamPrepV4SourceMapPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <ExamPrepV4SourceMapEditor projectId={Number(projectId)} />;
}
