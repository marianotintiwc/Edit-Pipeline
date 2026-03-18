import { Button, SurfaceCard } from "../primitives";

const TEMPLATE_CSV = "geo,subtitle_mode,clips[0].type,clips[0].url\nMLA,auto,scene,https://example.com/scene1.mp4\n";

export function CsvTemplateGenerator() {
  const handleDownloadTemplate = () => {
    const blob = new Blob([TEMPLATE_CSV], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "batch_template.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <SurfaceCard>
      <span className="section-header">CSV template</span>
      <h3>Start from a valid structure</h3>
      <p className="helper">Download a starter template to reduce mapping and validation issues.</p>
      <Button variant="secondary" onClick={handleDownloadTemplate}>
        Download template
      </Button>
    </SurfaceCard>
  );
}
