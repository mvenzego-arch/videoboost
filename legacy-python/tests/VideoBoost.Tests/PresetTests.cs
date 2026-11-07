using Xunit;
using VideoBoost.Engine;

namespace VideoBoost.Tests;

/// <summary>Пресеты и уровни качества — числа из legacy engine.py (ветка legacy-python).</summary>
public class PresetTests
{
    [Fact]
    public void Fast_MatchesLegacyNumbers()
    {
        var p = Presets.Fast;
        Assert.Equal("fast", p.Key);
        Assert.Equal(2, p.Scale);
        Assert.False(p.Interpolate);
        Assert.Equal(60, p.TargetFps);
        Assert.Equal(EncoderKind.AmfH264, p.Encoder);
        Assert.Equal(QualityKind.Speed, p.Quality);
        Assert.Equal(256, p.Tile);
    }

    [Fact]
    public void Balanced_MatchesLegacyNumbers()
    {
        var p = Presets.Balanced;
        Assert.Equal(2, p.Scale);
        Assert.True(p.Interpolate);
        Assert.Equal(60, p.TargetFps);
        Assert.Equal(EncoderKind.AmfHevc, p.Encoder);
        Assert.Equal(QualityKind.Balanced, p.Quality);
        Assert.Equal(384, p.Tile);
    }

    [Fact]
    public void Max_MatchesLegacyNumbers()
    {
        var p = Presets.Max;
        Assert.Equal(4, p.Scale);
        Assert.True(p.Interpolate);
        Assert.Equal(60, p.TargetFps);
        Assert.Equal(EncoderKind.AmfHevc, p.Encoder);
        Assert.Equal(QualityKind.Quality, p.Quality);
        Assert.Equal(512, p.Tile);
    }

    [Theory]
    [InlineData(0, 26, 23)]   // speed
    [InlineData(1, 22, 21)]   // balanced
    [InlineData(2, 19, 18)]   // quality
    public void QualityLevels_MatchLegacy(int kind, int qp, int crf)
    {
        var levels = Presets.QualityLevels((QualityKind)kind);
        Assert.Equal((qp, crf), levels);
    }

    [Fact]
    public void ByKey_ReturnsKnown_AndThrowsOnUnknown()
    {
        Assert.Equal(Presets.Fast, Presets.ByKey("fast"));
        Assert.Equal(Presets.Balanced, Presets.ByKey("balanced"));
        Assert.Equal(Presets.Max, Presets.ByKey("max"));
        Assert.Throws<ArgumentOutOfRangeException>(() => Presets.ByKey("nonexistent"));
    }
}
