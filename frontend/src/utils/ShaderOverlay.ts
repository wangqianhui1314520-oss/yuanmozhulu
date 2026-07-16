/**
 * 竹简舆图着色器叠加层 V2.0
 *
 * 在 Konva Canvas2D 地图上叠加 WebGL2 后处理效果，纯视觉增强，
 * 不影响任何游戏逻辑和鼠标交互。基于 shader-dev skill 技法。
 *
 * 效果列表：
 * - 域扭曲暗角    (Domain-Warped Vignette, 参考 domain-warping.md)
 * - 竹简噪点      (Parchment Grain + 域扭曲增强)
 * - 时序微光      (Ambient Warm Glow)
 * - 边缘做旧      (Edge Weathering + 域扭曲)
 * - Voronoi 墨点  (Voronoi Ink Spots, 参考 voronoi-cellular-noise.md)
 * - 云纹装饰      (Cloud Motif, 参考 procedural-2d-pattern.md)
 * - 余弦调色      (Cosine Palette Toning, 参考 color-palette.md)
 *
 * 使用方式：
 *   const overlay = new ShaderOverlay(canvas)
 *   overlay.start()
 *   // 运行时调参：overlay.intensity = 0.6; overlay.inkBleed = 0.3;
 *   // 停用时： overlay.stop()
 */

// ============================================================
// Shader 源码
// ============================================================

const VERTEX_SHADER = `#version 300 es
in vec2 a_position;
out vec2 v_uv;
void main() {
    v_uv = a_position * 0.5 + 0.5;
    gl_Position = vec4(a_position, 0.0, 1.0);
}`

const FRAGMENT_SHADER = `#version 300 es
precision highp float;

in vec2 v_uv;
out vec4 fragColor;

uniform float u_time;
uniform vec2  u_resolution;
uniform float u_intensity;     // 效果总强度 0~1
uniform float u_vignette;      // 暗角强度
uniform float u_noise;         // 噪点强度
uniform float u_glow;          // 微光强度
uniform float u_weathering;    // 做旧强度
uniform float u_inkBleed;      // Voronoi 墨点
uniform float u_cloudMotif;    // 云纹
uniform float u_waterRipple;   // 水纹

// ============ 基础噪声函数 ============

// Sin-free hash (Dave Hoskins)
float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

// 2D 值噪声
float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(
        mix(hash12(i + vec2(0.0, 0.0)), hash12(i + vec2(1.0, 0.0)), f.x),
        mix(hash12(i + vec2(0.0, 1.0)), hash12(i + vec2(1.0, 1.0)), f.x),
        f.y
    );
}

// ============ 域扭曲系统 (参考 domain-warping.md) ============

// 旋转矩阵 (≈36.87°, 标准去相关变换)
const mat2 rot = mat2(0.80, 0.60, -0.60, 0.80);

// 带旋转去相关的 FBM
float fbm(vec2 p) {
    float f = 0.0;
    f += 0.500000 * noise(p); p = rot * p * 2.02;
    f += 0.250000 * noise(p); p = rot * p * 2.03;
    f += 0.125000 * noise(p); p = rot * p * 2.01;
    f += 0.062500 * noise(p);
    return f / 0.9375;
}

// 域扭曲：f(p) -> f(p + fbm(p))
float domainWarp(vec2 p) {
    vec2 q = vec2(fbm(p + vec2(0.0, 0.0)), fbm(p + vec2(5.2, 1.3)));
    vec2 r = vec2(fbm(p + 4.0 * q + vec2(1.7, 9.2)), fbm(p + 4.0 * q + vec2(8.3, 2.8)));
    return fbm(p + 4.0 * r);
}

// ============ Voronoi 墨点 (参考 voronoi-cellular-noise.md) ============

vec2 hash22(vec2 p) {
    float n = sin(dot(p, vec2(127.1, 311.7)));
    return fract(vec2(262144.0, 32768.0) * n);
}

// 返回 F1 距离
float voronoi(vec2 x) {
    vec2 n = floor(x);
    vec2 f = fract(x);
    float m = 8.0;

    for (int j = -1; j <= 1; j++)
    for (int i = -1; i <= 1; i++) {
        vec2 g = vec2(float(i), float(j));
        vec2 o = hash22(n + g);
        vec2 r = g - f + o;
        float d = dot(r, r);
        if (d < m) m = d;
    }
    return sqrt(m);
}

// Voronoi 水墨晕染 — 域扭曲 + 细胞噪声结合
float voronoiInkBleed(vec2 uv, float time, float strength) {
    // 域扭曲输入坐标
    vec2 warped = uv + fbm(uv * 3.0 + time * 0.05) * 0.15;

    // 大尺度 Voronoi 墨点
    float v1 = voronoi(warped * 5.0) * 2.5;
    v1 = smoothstep(0.28, 0.42, v1);

    // 小尺度补充墨点
    float v2 = voronoi((warped + 0.3) * 9.0) * 2.0;
    v2 = smoothstep(0.22, 0.36, v2);

    // 极微墨点（飞白效果）
    float v3 = voronoi((warped - 0.15) * 17.0) * 1.8;
    v3 = smoothstep(0.18, 0.30, v3);

    // 噪声遮罩（不是均匀分布）
    float mask = fbm(uv * 2.5) * 0.8 + 0.2;
    mask *= fbm(uv * 5.0 + 1.7) * 0.6 + 0.4;

    float result = max(max(v1 * 0.6, v2 * 0.3), v3 * 0.15);
    result *= mask;

    return result * strength;
}

// ============ 云纹装饰 (参考 procedural-2d-pattern.md) ============

// 中国传统云纹 — 同心弧图案
float cloudMotifPattern(vec2 uv, float time, float strength) {
    // 六边形域重复（与地图网格呼应）
    const vec2 s = vec2(1.0, 1.7320508);
    vec2 p = uv * 12.0;

    // 六边形网格坐标
    vec4 hC = floor(vec4(p, p - vec2(0.5, 1.0)) / s.xyxy) + 0.5;
    vec4 h = vec4(p - hC.xy * s, p - (hC.zw + 0.5) * s);
    vec4 hexData = dot(h.xy, h.xy) < dot(h.zw, h.zw)
        ? vec4(h.xy, hC.xy)
        : vec4(h.zw, hC.zw + vec2(0.5, 1.0));

    vec2 hexUV = hexData.xy;
    float hexDist = length(hexUV);
    float hexAngle = atan(hexUV.y, hexUV.x);

    // 同心弧：每 30° 一段弧
    float arc = sin(hexAngle * 6.0 + time * 0.1) * 0.5 + 0.5;

    // 多层同心环
    float ring1 = smoothstep(0.18, 0.15, hexDist);
    float ring2 = smoothstep(0.32, 0.29, hexDist) * 0.6;
    float ring3 = smoothstep(0.44, 0.41, hexDist) * 0.3;

    float pattern = max(ring1, max(ring2, ring3)) * arc;

    // 只在角落显示（中心渐隐）
    float cornerMask = smoothstep(0.25, 0.6, length(uv - 0.5)) * 0.7 + 0.3;
    pattern *= cornerMask;

    // 微弱的呼吸动画
    pattern *= 0.5 + 0.5 * sin(time * 0.2 + uv.x * 3.0);

    return pattern * strength * 0.08;
}

// ============ 水纹 (参考 domain-warping.md) ============

float waterRipplePattern(vec2 uv, float time, float strength) {
    // 域扭曲波纹
    vec2 warped = uv;
    // 多层正弦波纹
    float r1 = sin((uv.x * 20.0 + fbm(uv * 3.0 + time * 0.1) * 2.0)) * 0.5 + 0.5;
    float r2 = sin((uv.y * 21.0 + fbm(uv * 3.5 - time * 0.08) * 2.0)) * 0.5 + 0.5;
    float r3 = sin((uv.x + uv.y) * 15.0 + time * 0.15) * 0.5 + 0.5;

    float ripple = (r1 * 0.4 + r2 * 0.35 + r3 * 0.25);

    // 柔和的边缘衰减
    float edgeFade = 1.0 - smoothstep(0.65, 1.0, length(uv - 0.5));

    return ripple * strength * 0.04 * edgeFade;
}

// ============ 增强版效果 ============

// 域扭曲水墨暗角 — 比 V1 更有机
float inkVignette(vec2 uv, float strength) {
    vec2 d = uv - 0.5;
    float dist = length(d) * 1.5;

    // 域扭曲让暗角边界不规则
    float warp = domainWarp(uv * 4.0 + u_time * 0.015) * 0.1;
    dist += warp;

    float vig = smoothstep(0.18, 1.05, dist);
    return vig * strength;
}

// 域扭曲增强噪点
float parchmentGrain(vec2 uv, float time, float strength) {
    float g1 = hash12(uv * 800.0 + vec2(time * 0.3, time * 0.7)) * 0.06;
    float g2 = hash12(uv * 400.0 - vec2(time * 0.5, time * 0.2)) * 0.04;
    float g3 = noise(uv * 150.0 + time * 0.01) * 0.03;

    // 域扭曲纵向竹纹
    float warpV = fbm(vec2(uv.y * 8.0, uv.x * 4.0 + time * 0.01)) * 0.3;
    float vertical = sin((uv.x + warpV) * 120.0) * 0.015;
    vertical += sin(uv.x * 37.0 + uv.y * 11.0) * 0.01;

    return (g1 + g2 + g3 + vertical) * strength;
}

// 烛光微光（保持简洁）
float ambientGlow(vec2 uv, float time, float strength) {
    vec2 center = vec2(0.5, 0.5);
    float dist = length(uv - center);
    float glow = exp(-dist * 2.5) * 0.15;

    float breath = sin(time * 0.4) * 0.03 + cos(time * 0.7) * 0.02;
    glow += breath * (1.0 - dist);

    float lr = (uv.x - 0.5) * 0.04;
    glow += lr * (1.0 - dist * 2.0);

    return glow * strength;
}

// 域扭曲边缘做旧
float edgeWeathering(vec2 uv, float time, float strength) {
    float edgeDist = min(min(uv.x, 1.0 - uv.x), min(uv.y, 1.0 - uv.y));
    float edge = smoothstep(0.0, 0.14, edgeDist);

    // 域扭曲取代原 FBM
    float wear = domainWarp(uv * 3.0 + time * 0.02) * 0.55;
    edge = clamp(edge + wear * (1.0 - edge), 0.0, 1.0);

    return edge * strength;
}

// ============ 余弦调色 (参考 color-palette.md) ============

// 古纸暖色调 — 使用余弦调色板
vec3 parchmentTone(vec3 col, float strength) {
    // 经典暖色调色板: a=0.5, b=0.5, c=1.0, d=(0.0, 0.10, 0.20)
    float t = dot(col, vec3(0.299, 0.587, 0.114));
    vec3 a = vec3(0.5);
    vec3 b = vec3(0.5);
    vec3 c = vec3(1.0);
    vec3 d = vec3(0.0, 0.10, 0.20);

    vec3 paletteCol = a + b * cos(6.28318 * (c * t + d));

    return mix(col, paletteCol, 0.15 * strength);
}

// ============ 主函数 ============

void main() {
    vec2 uv = v_uv;

    float I = u_intensity;

    // === 竹简中调底色（0.30-0.45 区间，使 overlay 混合的双向效果更明显）===
    vec3 base = vec3(0.35, 0.30, 0.22);
    float centerDist = length(uv - 0.5);
    base = mix(base, base * 1.18, exp(-centerDist * 3.0));

    vec3 col = base;

    // === 1. 域扭曲水墨暗角 — 向深色拉 ===
    float vignetteMask = inkVignette(uv, u_vignette * I);
    vec3 darkCorner = base * 0.25;  // 极深暗角，确保 overlay 乘法生效
    col = mix(col, darkCorner, vignetteMask);

    // === 2. 域扭曲竹简噪点 — ±微小扰动 ===
    float grain = parchmentGrain(uv, u_time, u_noise * I);
    col += grain * 1.2;  // 略增强噪点幅度

    // === 3. Voronoi 墨点晕染 — 深墨色斑 ===
    float splatter = voronoiInkBleed(uv, u_time, u_inkBleed * I);
    vec3 inkColor = vec3(0.06, 0.05, 0.035);
    col = mix(col, inkColor, splatter * 0.75);

    // === 4. 时序微光 — 暖金提亮 ===
    float glow = ambientGlow(uv, u_time, u_glow * I) * (1.0 - splatter * 0.5);
    // 微光取偏亮暖色（>0.5 触发 overlay 屏幕模式）
    vec3 warmGlow = vec3(0.78, 0.65, 0.35) * glow * 0.55;
    col += warmGlow;

    // === 5. 域扭曲边缘做旧 — 边缘褪色 ===
    float weathering = edgeWeathering(uv, u_time, u_weathering * I);
    vec3 worn = base * 0.45;
    col = mix(col, worn, weathering * 0.6);

    // === 6. 云纹装饰 — 淡金纹样（>0.5 触发屏幕）===
    float cloud = cloudMotifPattern(uv, u_time, u_cloudMotif * I);
    vec3 cloudColor = vec3(0.72, 0.62, 0.42);
    col = mix(col, cloudColor, cloud * 0.45);

    // === 7. 水纹 — 微青 ===
    float ripple = waterRipplePattern(uv, u_time, u_waterRipple * I);
    vec3 waterColor = base * 1.28 + vec3(0.0, 0.04, 0.07);
    col = mix(col, waterColor, ripple * 0.38);

    // === 8. 余弦调色 ===
    col = parchmentTone(col, 0.55 * I);

    // === 输出 ===
    // alpha=1.0（逐像素透明由 CSS opacity 控制，避免 premultipliedAlpha
    // 与 CSS mix-blend-mode:overlay 的兼容问题）
    col = clamp(col, 0.0, 1.0);

    // 确保所有 uniform 都被使用（防止编译器优化）
    float _t = u_time * 0.0001 + float(u_resolution.x) * 0.000001;

    fragColor = vec4(col, 1.0 + _t);
}`

// ============================================================
// ShaderOverlay 主类
// ============================================================

export class ShaderOverlay {
    private canvas: HTMLCanvasElement
    private gl: WebGL2RenderingContext | null = null
    private program: WebGLProgram | null = null
    private vao: WebGLVertexArrayObject | null = null

    private animFrameId: number = 0
    private startTime: number = 0
    private _running = false

    // Uniform locations
    private uTime: WebGLUniformLocation | null = null
    private uResolution: WebGLUniformLocation | null = null
    private uIntensity: WebGLUniformLocation | null = null
    private uVignette: WebGLUniformLocation | null = null
    private uNoise: WebGLUniformLocation | null = null
    private uGlow: WebGLUniformLocation | null = null
    private uWeathering: WebGLUniformLocation | null = null
    private uInkBleed: WebGLUniformLocation | null = null
    private uCloudMotif: WebGLUniformLocation | null = null
    private uWaterRipple: WebGLUniformLocation | null = null

    // 效果参数（可运行时调整，均 0~1）
    public intensity = 1.0       // 总强度
    public vignette = 0.70       // 域扭曲暗角
    public grainNoise = 0.55     // 竹简噪点
    public glow = 0.65           // 烛光微光
    public weathering = 0.45     // 边缘做旧
    public inkBleed = 0.40       // Voronoi 墨点
    public cloudMotif = 0.50     // 云纹
    public waterRipple = 0.35    // 水纹

    constructor(canvas: HTMLCanvasElement) {
        this.canvas = canvas
    }

    /** 初始化 WebGL2 上下文和着色器 */
    init(): boolean {
        const gl = this.canvas.getContext('webgl2', {
            alpha: true,
            premultipliedAlpha: false,    // CSS mix-blend-mode 需要非预乘颜色
            antialias: false,
            powerPreference: 'low-power',
        })

        if (!gl) {
            console.warn('[ShaderOverlay] WebGL2 不可用，着色器叠加层禁用')
            return false
        }

        this.gl = gl

        // 编译着色器
        const vs = this._compileShader(gl.VERTEX_SHADER, VERTEX_SHADER)
        const fs = this._compileShader(gl.FRAGMENT_SHADER, FRAGMENT_SHADER)
        if (!vs || !fs) return false

        // 链接着色器程序
        const program = gl.createProgram()!
        gl.attachShader(program, vs)
        gl.attachShader(program, fs)
        gl.linkProgram(program)

        if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
            console.error('[ShaderOverlay] 程序链接失败:', gl.getProgramInfoLog(program))
            gl.deleteProgram(program)
            return false
        }

        this.program = program

        // 获取 uniform 位置
        this.uTime = gl.getUniformLocation(program, 'u_time')
        this.uResolution = gl.getUniformLocation(program, 'u_resolution')
        this.uIntensity = gl.getUniformLocation(program, 'u_intensity')
        this.uVignette = gl.getUniformLocation(program, 'u_vignette')
        this.uNoise = gl.getUniformLocation(program, 'u_noise')
        this.uGlow = gl.getUniformLocation(program, 'u_glow')
        this.uWeathering = gl.getUniformLocation(program, 'u_weathering')
        this.uInkBleed = gl.getUniformLocation(program, 'u_inkBleed')
        this.uCloudMotif = gl.getUniformLocation(program, 'u_cloudMotif')
        this.uWaterRipple = gl.getUniformLocation(program, 'u_waterRipple')

        // 设置全屏四边形
        const positions = new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1])
        const vao = gl.createVertexArray()!
        gl.bindVertexArray(vao)

        const buffer = gl.createBuffer()!
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
        gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW)

        const posLoc = gl.getAttribLocation(program, 'a_position')
        gl.enableVertexAttribArray(posLoc)
        gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0)

        this.vao = vao

        // 设置混合模式
        gl.enable(gl.BLEND)
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA)

        this.startTime = performance.now()
        return true
    }

    /** 开始渲染循环 */
    start(): void {
        if (!this.gl || !this.program) {
            const ok = this.init()
            if (!ok) return
        }
        if (this._running) return
        this._running = true
        this._render()
    }

    /** 停止渲染循环 */
    stop(): void {
        this._running = false
        if (this.animFrameId) {
            cancelAnimationFrame(this.animFrameId)
            this.animFrameId = 0
        }
        // 清除画布
        if (this.gl) {
            this.gl.clear(this.gl.COLOR_BUFFER_BIT)
        }
    }

    /** 销毁实例，释放 GPU 资源 */
    destroy(): void {
        this.stop()
        if (this.gl && this.program) {
            this.gl.deleteProgram(this.program)
            this.program = null
        }
        this.gl = null
    }

    get running(): boolean {
        return this._running
    }

    // ---- 内部方法 ----

    private _compileShader(type: number, source: string): WebGLShader | null {
        const gl = this.gl!
        const shader = gl.createShader(type)!
        gl.shaderSource(shader, source)
        gl.compileShader(shader)

        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
            console.error('[ShaderOverlay] 着色器编译失败:', gl.getShaderInfoLog(shader))
            gl.deleteShader(shader)
            return null
        }
        return shader
    }

    private _render = (): void => {
        if (!this._running) return

        const gl = this.gl!
        const canvas = this.canvas

        // 同步 canvas 尺寸（含 devicePixelRatio 以匹配 Konva 高清渲染）
        const dpr = window.devicePixelRatio || 1
        const displayWidth = canvas.clientWidth
        const displayHeight = canvas.clientHeight
        const pixelWidth = Math.round(displayWidth * dpr)
        const pixelHeight = Math.round(displayHeight * dpr)

        if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
            canvas.width = pixelWidth
            canvas.height = pixelHeight
            gl.viewport(0, 0, pixelWidth, pixelHeight)
        }

        gl.useProgram(this.program!)

        // 更新 uniforms
        const elapsed = (performance.now() - this.startTime) * 0.001
        gl.uniform1f(this.uTime!, elapsed)
        gl.uniform2f(this.uResolution!, canvas.width, canvas.height)
        gl.uniform1f(this.uIntensity!, this.intensity)
        gl.uniform1f(this.uVignette!, this.vignette)
        gl.uniform1f(this.uNoise!, this.grainNoise)
        gl.uniform1f(this.uGlow!, this.glow)
        gl.uniform1f(this.uWeathering!, this.weathering)
        gl.uniform1f(this.uInkBleed!, this.inkBleed)
        gl.uniform1f(this.uCloudMotif!, this.cloudMotif)
        gl.uniform1f(this.uWaterRipple!, this.waterRipple)

        // 绘制全屏四边形
        gl.bindVertexArray(this.vao)
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4)

        this.animFrameId = requestAnimationFrame(this._render)
    }
}
