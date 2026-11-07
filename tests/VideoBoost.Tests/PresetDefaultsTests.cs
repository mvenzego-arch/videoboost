using VideoBoost.Engine;

namespace VideoBoost.Tests;

/// <summary>Проверки дефолтов пресетов против legacy-значений engine.py.</summary>
public sealed class PresetDefaultsTests
{
    [Theory]
    [InlineData(PresetKind.Fast, "Быстро", ScaleMode.X2, ModelMode.Light, false,
        FpsMode.Fps60, EncoderMode.AmfH264, QualityMode.Speed, TileMode.T256)]
    [InlineData(PresetKind.Balanced, "Баланс", ScaleMode.X2, ModelMode.Light, true,
        FpsMode.Fps60, EncoderMode.AmfHevc, QualityMode.Balanced, TileMode.T384)]
    [InlineData(PresetKind.Max, "Максимально", ScaleMode.X4, ModelMode.Heavy, true,
        FpsMode.Fps60, EncoderMode.AmfHevc, QualityMode.Max, TileMode.T512)]
    public void Presets_MatchLegacyEngineNumbers(
        PresetKind kind,
        string title,
        ScaleMode scale,
        ModelMode model,
        bool interpolate,
        FpsMode fps,
        EncoderMode encoder,
        QualityMode quality,
        TileMode tile)
    {
        var preset = PresetDefaults.For(kind);

        Assert.Equal(kind, preset.Kind);
        Assert.Equal(title, preset.Title);
        Assert.Equal(scale, preset.Scale);
        Assert.Equal(model, preset.Model);
        Assert.Equal(interpolate, preset.Interpolate);
        Assert.Equal(fps, preset.Fps);
        Assert.Equal(encoder, preset.Encoder);
        Assert.Equal(quality, preset.Quality);
        Assert.Equal(tile, preset.Tile);
        Assert.True(preset.SaveSpace);
        Assert.Equal(60, preset.TargetFps);
    }

    [Fact]
    public void Presets_DescriptionsAndOrder_MatchLegacy()
    {
        Assert.Equal(
            "Апскейл x2 (1080p → 4K) лёгкой моделью, H.264 на GPU, без интерполяции. "
                + "Самый быстрый вариант: ~1 час на 1 минуту видео 1080p.",
            PresetDefaults.Fast.Description);
        Assert.Equal(
            "Апскейл x2 (1080p → 4K) + плавность до 60 FPS, HEVC. "
                + "Оптимальный выбор: ~1–2 часа на 1 минуту видео 1080p.",
            PresetDefaults.Balanced.Description);
        Assert.Equal(
            "Апскейл x4 (1080p → 8K!) тяжёлой моделью + 60 FPS, максимум качества. "
                + "На RX 570 очень медленно: десятки часов на 1 минуту видео.",
            PresetDefaults.Max.Description);

        Assert.Equal(
            new[] { PresetKind.Fast, PresetKind.Balanced, PresetKind.Max },
            PresetDefaults.All.Select(preset => preset.Kind).ToArray());
        Assert.Equal(2, PresetDefaults.Balanced.ScaleFactor);
        Assert.Equal(4, PresetDefaults.Max.ScaleFactor);
    }

    [Fact]
    public void For_ReturnsSamePresetInstance()
    {
        Assert.Same(PresetDefaults.Fast, PresetDefaults.For(PresetKind.Fast));
        Assert.Same(PresetDefaults.Balanced, PresetDefaults.For(PresetKind.Balanced));
        Assert.Same(PresetDefaults.Max, PresetDefaults.For(PresetKind.Max));
    }
}
