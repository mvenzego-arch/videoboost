using VideoBoost.Engine;

namespace VideoBoost.Tests;

/// <summary>VideoInfo — чистый DTO без файлового IO.</summary>
public sealed class VideoInfoTests
{
    [Fact]
    public void VideoInfo_CarriesProbeFields_IncludingCyrillicPath()
    {
        var path = Path.Combine(@"E:\Видео", "тест 1.mp4");

        var info = new VideoInfo(
            path,
            Width: 1920,
            Height: 1080,
            Fps: 29.97,
            Duration: 125.5,
            AudioCodec: "aac",
            IsHdr: true,
            FramesHint: 3760);

        Assert.Equal(path, info.Path);
        Assert.Equal(1920, info.Width);
        Assert.Equal(1080, info.Height);
        Assert.Equal(29.97, info.Fps);
        Assert.Equal(125.5, info.Duration);
        Assert.Equal("aac", info.AudioCodec);
        Assert.True(info.IsHdr);
        Assert.Equal(3760, info.FramesHint);
        Assert.True(info.HasAudio);
        Assert.Equal(1920L * 1080L, info.PixelCount);
    }

    [Fact]
    public void VideoInfo_WithoutAudio_ReportsNoAudio()
    {
        var info = new VideoInfo(
            Path.Combine("C:", "video.mp4"),
            Width: 1280,
            Height: 720,
            Fps: 60,
            Duration: 10,
            AudioCodec: null,
            IsHdr: false);

        Assert.False(info.HasAudio);
        Assert.False(info.IsHdr);
        Assert.Equal(0, info.FramesHint);
    }
}
