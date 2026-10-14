/* Copyright (C) 2026 The MegaMek Team. SPDX-License-Identifier: GPL-3.0-or-later */
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.imageio.ImageIO;

/**
 * Rebuild the aligned ice maps from the preserved generated color source. Java 21 source launcher.
 *
 * <p>Features inside the ice (cloudiness, cracks, bubbles) are separated by scale into their own channels. The polished
 * top surface only undulates gently, so the normal map comes from the broad field alone: a crack under the surface is
 * not a groove in it.
 */
public class GenerateIceMaps {
    static double luma(int rgb) {
        return (((rgb >> 16) & 255) * .299 + ((rgb >> 8) & 255) * .587 + (rgb & 255) * .114) / 255;
    }

    static int byteValue(double value) { return (int) Math.round(Math.clamp(value, 0, 1) * 255); }

    static int rgb(double r, double g, double b) {
        return 0xff000000 | byteValue(r) << 16 | byteValue(g) << 8 | byteValue(b);
    }

    static double linear(double value) {
        return value <= .04045 ? value / 12.92 : Math.pow((value + .055) / 1.055, 2.4);
    }

    static double display(double value) {
        return value <= .0031308 ? value * 12.92 : 1.055 * Math.pow(value, 1 / 2.4) - .055;
    }

    /** Catmull-Rom bicubic interpolation, evaluated on linear RGB rather than encoded image bytes. */
    static double cubic(double distance) {
        double x = Math.abs(distance);
        if (x < 1) { return (1.5 * x - 2.5) * x * x + 1; }
        return x < 2 ? ((-.5 * x + 2.5) * x - 4) * x + 2 : 0;
    }

    static double[] resizeColor(BufferedImage source, int size) {
        int width = source.getWidth(), height = source.getHeight();
        double scaleX = Math.max(1, width / (double) size), scaleY = Math.max(1, height / (double) size);
        double[] input = new double[width * height * 3], output = new double[size * size * 3];
        double[] decoded = new double[256];
        for (int i = 0; i < decoded.length; i++) { decoded[i] = linear(i / 255.0); }
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                int pixel = source.getRGB(x, y);
                for (int channel = 0; channel < 3; channel++) {
                    input[(y * width + x) * 3 + channel] = decoded[(pixel >> (16 - channel * 8)) & 255];
                }
            }
        }
        for (int y = 0; y < size; y++) {
            double sy = (y + .5) * height / size - .5;
            for (int x = 0; x < size; x++) {
                double sx = (x + .5) * width / size - .5;
                int target = (y * size + x) * 3;
                double total = 0;
                // Widen the footprint when shrinking: interpolation alone aliases detail above the target Nyquist.
                for (int iy = (int) Math.ceil(sy - 2 * scaleY); iy <= Math.floor(sy + 2 * scaleY); iy++) {
                    int py = Math.clamp(iy, 0, height - 1);
                    double wy = cubic((sy - iy) / scaleY);
                    for (int ix = (int) Math.ceil(sx - 2 * scaleX); ix <= Math.floor(sx + 2 * scaleX); ix++) {
                        int px = Math.clamp(ix, 0, width - 1), origin = (py * width + px) * 3;
                        double weight = wy * cubic((sx - ix) / scaleX);
                        total += weight;
                        for (int channel = 0; channel < 3; channel++) {
                            output[target + channel] += input[origin + channel] * weight;
                        }
                    }
                }
                for (int channel = 0; channel < 3; channel++) { output[target + channel] /= total; }
            }
        }
        return output;
    }

    static double seamWeight(int along, int size) {
        double distance = Math.min(along, size - 1 - along) / (size * .25);
        double w = 1 - Math.clamp(distance, 0, 1);
        return w * w * (3 - 2 * w);
    }

    /** Keep both seam passes in linear floating-point RGB; encode only the finished color map. */
    static BufferedImage color(BufferedImage source, int size) {
        double[] current = resizeColor(source, size);
        for (int pass = 0; pass < 2; pass++) {
            double[] next = new double[current.length];
            for (int y = 0; y < size; y++) {
                for (int x = 0; x < size; x++) {
                    double weight = seamWeight(pass == 0 ? x : y, size);
                    int a = (y * size + x) * 3;
                    int b = (pass == 0 ? y * size + (x + size / 2) % size : (y + size / 2) % size * size + x) * 3;
                    for (int channel = 0; channel < 3; channel++) {
                        next[a + channel] = current[a + channel] * (1 - weight) + current[b + channel] * weight;
                    }
                }
            }
            current = next;
        }
        var result = new BufferedImage(size, size, BufferedImage.TYPE_INT_RGB);
        for (int y = 0; y < size; y++) {
            for (int x = 0; x < size; x++) {
                int i = (y * size + x) * 3;
                result.setRGB(x, y, rgb(display(current[i]), display(current[i + 1]), display(current[i + 2])));
            }
        }
        return result;
    }

    /** Separable box blur on the torus, so every derived field repeats as the color does. */
    static double[] blur(double[] field, int size, int radius) {
        double[] across = new double[field.length], result = new double[field.length];
        for (int pass = 0; pass < 2; pass++) {
            double[] from = pass == 0 ? field : across, to = pass == 0 ? across : result;
            for (int y = 0; y < size; y++) {
                for (int x = 0; x < size; x++) {
                    double sum = 0;
                    for (int k = -radius; k <= radius; k++) {
                        int sx = pass == 0 ? Math.floorMod(x + k, size) : x, sy = pass == 0 ? y : Math.floorMod(y + k, size);
                        sum += from[sy * size + sx];
                    }
                    to[y * size + x] = sum / (2 * radius + 1);
                }
            }
        }
        return result;
    }

    /**
     * Tile seamlessly: blend in a copy shifted by half the size, first across then down, weighted toward each shifted
     * copy only near the wrap where the original has its seam. Neither copy's seam lies under its own weight.
     */
    static BufferedImage seamless(BufferedImage image, int size) {
        BufferedImage current = image;
        for (int pass = 0; pass < 2; pass++) {
            BufferedImage next = new BufferedImage(size, size, BufferedImage.TYPE_INT_RGB);
            for (int y = 0; y < size; y++) {
                for (int x = 0; x < size; x++) {
                    double w = seamWeight(pass == 0 ? x : y, size);
                    int a = current.getRGB(x, y);
                    int b = pass == 0 ? current.getRGB((x + size / 2) % size, y) : current.getRGB(x, (y + size / 2) % size);
                    int result = 0xff000000;
                    for (int shift : new int[] {16, 8, 0}) {
                        result |= (int) Math.round(((a >> shift) & 255) * (1 - w) + ((b >> shift) & 255) * w) << shift;
                    }
                    next.setRGB(x, y, result);
                }
            }
            current = next;
        }
        return current;
    }

    public static void main(String[] args) throws Exception {
        BufferedImage source = ImageIO.read(Path.of(args[0]).toFile());
        Path output = Path.of(args[1]);
        Files.createDirectories(output);
        int size = 1024, mapSize = 512;
        BufferedImage resized = new BufferedImage(size, size, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = resized.createGraphics();
        g.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BICUBIC);
        g.drawImage(source, 0, 0, size, size, null);
        g.dispose();
        // Preserve the encoded-derived geometry recipe. These engineered fields must not change when the color
        // filtering is corrected; height, roughness, cloudiness and cracks are numerical channels, not radiance.
        BufferedImage dataSource = seamless(resized, size);
        BufferedImage small = new BufferedImage(mapSize, mapSize, BufferedImage.TYPE_INT_RGB);
        g = small.createGraphics();
        g.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BILINEAR);
        g.drawImage(dataSource, 0, 0, mapSize, mapSize, null);
        g.dispose();
        double[] luma = new double[mapSize * mapSize];
        for (int y = 0; y < mapSize; y++) {
            for (int x = 0; x < mapSize; x++) { luma[y * mapSize + x] = luma(small.getRGB(x, y)); }
        }
        double[] fine = blur(luma, mapSize, 2), cloud = blur(luma, mapSize, 7), broad = blur(luma, mapSize, 14);
        double mean = 0;
        for (double value : broad) { mean += value / broad.length; }
        BufferedImage normal = new BufferedImage(mapSize, mapSize, BufferedImage.TYPE_INT_RGB);
        BufferedImage surface = new BufferedImage(mapSize, mapSize, BufferedImage.TYPE_INT_ARGB);
        for (int y = 0; y < mapSize; y++) {
            for (int x = 0; x < mapSize; x++) {
                int i = y * mapSize + x;
                // Height: the broad undulation of the polished top, and the only source of its normal.
                double height = .5 + (broad[i] - mean) * 1.6;
                double nx = (broad[y * mapSize + Math.floorMod(x - 1, mapSize)] - broad[y * mapSize + (x + 1) % mapSize]) * 6;
                double ny = (broad[Math.floorMod(y - 1, mapSize) * mapSize + x] - broad[(y + 1) % mapSize * mapSize + x]) * 6;
                double length = Math.sqrt(nx * nx + ny * ny + 1);
                normal.setRGB(x, y, rgb(nx / length * .5 + .5, ny / length * .5 + .5, 1 / length * .5 + .5));
                // Cloudy ice: the scattering field at the scale of frost and bubble clouds.
                double cloudy = Math.clamp((cloud[i] - .36) / .42, 0, 1);
                // Cracks and bubbles: the bright features narrower than a few texels.
                double cracks = Math.clamp((fine[i] - cloud[i] - .015) / .10, 0, 1);
                // Engineered data maps, not measured scans: polished clear ice, rougher where frost clouds it.
                int properties = byteValue(height) << 16 | byteValue(.06 + cloudy * .26) << 8 | byteValue(cracks)
                      | byteValue(cloudy) << 24;
                surface.setRGB(x, y, properties);
            }
        }
        ImageIO.write(color(source, size), "png", output.resolve("sheet.png").toFile());
        ImageIO.write(normal, "png", output.resolve("sheet-normal.png").toFile());
        ImageIO.write(surface, "png", output.resolve("sheet-surface.png").toFile());
        System.out.println("Ice maps: 1024 color, 512 normal and 512 height/roughness/cracks/cloudy.");
    }
}
