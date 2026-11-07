using Microsoft.UI.Xaml;
using VideoBoost.Engine;

namespace VideoBoost.App;

public sealed partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
        Title = "VideoBoost v3";
    }

    private void OnAddVideo(object sender, RoutedEventArgs args)
    {
        var tools = new ToolPaths(
            FFmpeg: @"tools\ffmpeg.exe",
            FFprobe: @"tools\ffprobe.exe",
            Realesrgan: @"tools\realesrgan-ncnn-vulkan.exe",
            RealesrganModelsDir: @"tools\realesrgan\models",
            Rife: @"tools\rife-ncnn-vulkan.exe",
            RifeModel: @"tools\rife\models\rife-v4.6");

        var paths = new EnginePaths(
            FramesDir: @"temp\frames",
            UpscaledDir: @"temp\upscaled",
            SmoothDir: @"temp\smooth",
            ProgressFile: @"temp\progress.txt",
            PartPath: @"out\result.part.mp4");

        var plan = EnginePlanBuilder.Build(tools, @"Пример\Видео\тест.mp4", paths, Presets.Balanced, new PlanOptions());
        LogLine.Text = "План: " + string.Join(" → ", plan.Steps.Select(static s => s.Title));
    }
}
