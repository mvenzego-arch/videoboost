using Xunit;
using VideoBoost.Engine;
using VideoBoost.Engine.Commands;

namespace VideoBoost.Tests;

/// <summary>Флаги FFmpeg перенесены из legacy engine.py — сверяются дословно.</summary>
public class FFmpegCommandBuilderTests
{
    private static readonly ToolPaths Tools = new(
        FFmpeg: @"C:\tools\ffmpeg.exe",
        FFprobe: @"C:\tools\ffprobe.exe",
        Realesrgan: @"C:\tools\realesrgan\realesrgan-ncnn-vulkan.exe",
        RealesrganModelsDir: @"C:\tools\realesrgan\models",
        Rife: @"C:\tools\rife\rife-ncnn-vulkan.exe",
        RifeModel: @"C:\tools\rife\models\rife-v4.6");

    private const string Video = @"E:\Проверка папки\тест.mp4";
    private const string Frames = @"T:\frames";
    private const string Progress = @"T:\progress.txt";
    private const string Part = @"T:\out\result.part.mp4";

    [Fact]
    public void ExtractFrames_Jpg_UsesLegacyFlags()
    {
        var cmd = (List<string>)FFmpegCommandBuilder.ExtractFrames(Tools, Video, Frames, FrameFormat.Jpg, Progress);

        Assert.Equal(Tools.FFmpeg, cmd[0]);
        Assert.Contains("-y", cmd);
        Assert.Contains("-nostdin", cmd);
        Assert.Contains("-hide_banner", cmd);
        Assert.Equal("passthrough", cmd[cmd.IndexOf("-fps_mode") + 1]);
        Assert.Equal("1", cmd[cmd.IndexOf("-qscale:v") + 1]);
        Assert.Equal(Progress, cmd[cmd.IndexOf("-progress") + 1]);
        Assert.EndsWith("%06d.jpg", cmd[^1]);
    }

    [Fact]
    public void ExtractFrames_Png_OmitsQscale()
    {
        var cmd = (List<string>)FFmpegCommandBuilder.ExtractFrames(Tools, Video, Frames, FrameFormat.Png, Progress);
        Assert.Equal(-1, cmd.IndexOf("-qscale:v"));
        Assert.EndsWith("%06d.png", cmd[^1]);
    }

    [Theory]
    [InlineData("aac")]
    [InlineData("mp3")]
    [InlineData("ac3")]
    [InlineData("eac3")]
    [InlineData("alac")]
    public void AudioArgs_SafeCodecs_AreCopied(string codec)
    {
        var args = FFmpegCommandBuilder.AudioArgs(codec);
        Assert.Equal(new[] { "-c:a", "copy" }, args);
    }

    [Fact]
    public void AudioArgs_UnsafeCodec_TranscodesToAac192k()
    {
        var args = FFmpegCommandBuilder.AudioArgs("opus");
        Assert.Equal(new[] { "-c:a", "aac", "-b:a", "192k" }, args);
    }

    [Fact]
    public void AudioArgs_MissingTrack_IsDropped()
    {
        Assert.Equal(new[] { "-an" }, FFmpegCommandBuilder.AudioArgs(null));
        Assert.Equal(new[] { "-an" }, FFmpegCommandBuilder.AudioArgs(""));
    }

    [Fact]
    public void EncodeFrames_AmfHevc_UsesCqpAndHvc1Tag()
    {
        var plan = new EncodePlan(
            Tools, Video, Frames, FrameFormat.Jpg,
            Interpolated: true, OutFps: 60,
            Encoder: EncoderKind.AmfHevc, UseAmf: true, Quality: QualityKind.Balanced,
            Qp: 22, Crf: 21, AudioCodec: "aac",
            ProgressFile: Progress, PartPath: Part);

        var cmd = (List<string>)FFmpegCommandBuilder.EncodeFrames(plan);

        Assert.Equal(Tools.FFmpeg, cmd[0]);
        Assert.Equal("hevc_amf", cmd[cmd.IndexOf("-c:v") + 1]);
        Assert.Equal("balanced", cmd[cmd.IndexOf("-quality") + 1]);
        Assert.Equal("cqp", cmd[cmd.IndexOf("-rc") + 1]);
        Assert.Equal("22", cmd[cmd.IndexOf("-qp_i") + 1]);
        Assert.Equal("22", cmd[cmd.IndexOf("-qp_p") + 1]);
        Assert.Equal("hvc1", cmd[cmd.IndexOf("-tag:v") + 1]);
        Assert.Equal("60.000000", cmd[cmd.IndexOf("-framerate") + 1]);
        Assert.Equal("1", cmd[cmd.IndexOf("-start_number") + 1]);
        Assert.Equal(Path.Combine(Frames, "%08d.jpg"), cmd[cmd.IndexOf("-i") + 1]);
        Assert.Equal("yuv420p", cmd[cmd.IndexOf("-pix_fmt") + 1]);
        Assert.Equal("copy", cmd[cmd.IndexOf("-c:a") + 1]);
        Assert.Contains("+faststart", cmd);
        Assert.Equal(Part, cmd[^1]);
    }

    [Fact]
    public void EncodeFrames_AmfH264_NoHvc1Tag()
    {
        var plan = new EncodePlan(
            Tools, Video, Frames, FrameFormat.Jpg,
            Interpolated: false, OutFps: 60,
            Encoder: EncoderKind.AmfH264, UseAmf: true, Quality: QualityKind.Speed,
            Qp: 26, Crf: 23, AudioCodec: "aac",
            ProgressFile: Progress, PartPath: Part);

        var cmd = (List<string>)FFmpegCommandBuilder.EncodeFrames(plan);
        Assert.Equal("h264_amf", cmd[cmd.IndexOf("-c:v") + 1]);
        Assert.Equal(-1, cmd.IndexOf("-tag:v"));
        Assert.Equal(Path.Combine(Frames, "%06d.jpg"), cmd[cmd.IndexOf("-i") + 1]);
    }

    [Fact]
    public void EncodeFrames_Cpu_FallsBackToLibx264()
    {
        var plan = new EncodePlan(
            Tools, Video, Frames, FrameFormat.Jpg,
            Interpolated: false, OutFps: 30,
            Encoder: EncoderKind.Cpu, UseAmf: true, Quality: QualityKind.Balanced,
            Qp: 22, Crf: 21, AudioCodec: "aac",
            ProgressFile: Progress, PartPath: Part);

        var cmd = (List<string>)FFmpegCommandBuilder.EncodeFrames(plan);
        Assert.Equal("libx264", cmd[cmd.IndexOf("-c:v") + 1]);
        Assert.Equal("fast", cmd[cmd.IndexOf("-preset") + 1]);
        Assert.Equal("21", cmd[cmd.IndexOf("-crf") + 1]);
        Assert.Contains("yuv420p", cmd);
    }

    [Fact]
    public void EncodePaths_KeepCyrillicAndSpacesVerbatim()
    {
        var plan = new EncodePlan(
            Tools, Video, Frames, FrameFormat.Jpg,
            Interpolated: false, OutFps: 60,
            Encoder: EncoderKind.Cpu, UseAmf: false, Quality: QualityKind.Speed,
            Qp: 26, Crf: 23, AudioCodec: null,
            ProgressFile: Progress, PartPath: Part);

        var cmd = (List<string>)FFmpegCommandBuilder.EncodeFrames(plan);
        Assert.Contains("-an", cmd);
        Assert.Contains(Video, cmd);
    }
}
