using Xunit;
using VideoBoost.Engine;
using VideoBoost.Engine.Commands;

namespace VideoBoost.Tests;

/// <summary>Real-ESRGAN / RIFE: дословный порядок флагов из legacy engine.py.</summary>
public class ToolBuildersTests
{
    private static readonly ToolPaths Tools = new(
        FFmpeg: @"C:\tools\ffmpeg.exe",
        FFprobe: @"C:\tools\ffprobe.exe",
        Realesrgan: @"C:\tools\realesrgan\realesrgan-ncnn-vulkan.exe",
        RealesrganModelsDir: @"C:\tools\realesrgan\models",
        Rife: @"C:\tools\rife\rife-ncnn-vulkan.exe",
        RifeModel: @"C:\tools\rife\models\rife-v4.6");

    [Fact]
    public void Upscale_ExactLegacySequence()
    {
        var plan = new UpscalePlan(Tools, @"T:\frames", @"T:\upscaled", 2, "realesr-animevideov3", 256, FrameFormat.Jpg);
        var cmd = (List<string>)EsrganCommandBuilder.Upscale(plan);
        Assert.Equal(new[]
        {
            Tools.Realesrgan, "-i", @"T:\frames", "-o", @"T:\upscaled", "-s", "2",
            "-n", "realesr-animevideov3", "-m", Tools.RealesrganModelsDir, "-t", "256",
            "-g", "0", "-j", "1:1:1", "-f", "jpg",
        }, cmd);
    }

    [Fact]
    public void Upscale_PngFormat_InOutputFlag()
    {
        var plan = new UpscalePlan(Tools, @"T:\frames", @"T:\upscaled", 4, "realesrgan-x4plus", 384, FrameFormat.Png);
        var cmd = (List<string>)EsrganCommandBuilder.Upscale(plan);
        Assert.Equal("png", cmd[^1]);
        Assert.Equal("4", cmd[cmd.IndexOf("-s") + 1]);
        Assert.Equal("384", cmd[cmd.IndexOf("-t") + 1]);
    }

    [Fact]
    public void ResolveModel_AutoMax_HeavyByOption()
    {
        Assert.Equal("realesrgan-x4plus", EsrganCommandBuilder.ResolveModel(ModelMode.Auto, ContentKind.General, 4, Presets.Max));
        Assert.Equal("realesrgan-x4plus-anime", EsrganCommandBuilder.ResolveModel(ModelMode.Auto, ContentKind.Anime, 4, Presets.Max));
    }

    [Fact]
    public void ResolveModel_HeavyBelowScale4_DegradesToLight()
    {
        Assert.Equal("realesr-animevideov3", EsrganCommandBuilder.ResolveModel(ModelMode.Heavy, ContentKind.General, 2, Presets.Balanced));
        Assert.Equal("realesr-animevideov3", EsrganCommandBuilder.ResolveModel(ModelMode.Light, ContentKind.Anime, 4, Presets.Max));
    }

    [Fact]
    public void Interpolate_ExactLegacySequence()
    {
        var plan = new InterpolatePlan(Tools, @"T:\upscaled", @"T:\smooth", 90, FrameFormat.Jpg, UltraHd: false);
        var cmd = (List<string>)RifeCommandBuilder.Interpolate(plan);
        Assert.Equal(new[]
        {
            Tools.Rife, "-i", @"T:\upscaled", "-o", @"T:\smooth", "-n", "90",
            "-m", Tools.RifeModel, "-g", "0", "-j", "1:1:1", "-f", "%08d.jpg",
        }, cmd);
    }

    [Fact]
    public void Interpolate_UhdAppendsFlag()
    {
        var plan = new InterpolatePlan(Tools, @"T:\upscaled", @"T:\smooth", 60, FrameFormat.Png, UltraHd: true);
        var cmd = (List<string>)RifeCommandBuilder.Interpolate(plan);
        Assert.Equal("-u", cmd[^1]);
        Assert.Equal("%08d.png", cmd[cmd.IndexOf("-f") + 1]);
    }
}
