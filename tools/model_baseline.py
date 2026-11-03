"""stylize_v5_96 的 Python 参考模型（算法 v4），与 RTL 逐帧、逐像素一致。

用法（需要 numpy）：
  python model.py prep  <rgb24.raw> img_in.hex [W H]
  python model.py check img_in.hex <rtl_out.hex> <mode> <frames> <out.raw> [W H]
        # RTL 连续跑 frames 帧（同一幅图），逐帧比较（含参数自适应过程）
  python model.py demo  <rgb24.raw> <out_prefix>     # 参数收敛后的效果图

算法（三级 3x3 窗口）：
  第一级：3x3 高斯平滑 RGB -> B
  第二级（窗口在 B 上）：g = gray(B) 的 3x3 Sobel -> mag；B 再做 3x3 高斯 -> B2（等效 5x5），Y2 = gray(B2)
     卡通：band = Y2 落在 6 档中的哪一档（阈值 t1..t5 每帧自适应 = Y2 的 1/6..5/6 分位点）
           色差 c = (B2 - Y2) - 偏色平面 o(x,y)（常数 + 左右梯度 + 上下梯度，每帧自适应，
             用近中性像素估计；去掉整体偏暖/偏粉和镜头造成的左暖右紫）
           c' = sign(c) * min(255, (|c|-4)+ * g/8)（±4 以内归中性；g 每帧自适应 1.0~3.0，
             使平均色差约 9，接近自然照片的饱和度——板上画面饱和度偏低时自动补回来）
           edge = mag >= th（th 每帧自适应，约 7% 像素为线）
     素描：gray = 纸色 - ink（与 v3 相同，phi 自适应）
  第三级（窗口在 {band, edge, c'} 上）：
     卡通：band 取 3x3 中值（去掉色阶交界处的椒盐噪点），亮度 = 该档中点，
           out = 档位亮度 + c'（中心像素），中心像素是边缘则画黑线
     素描：取中心像素
空间对齐：输出第 y 行第 X 列 = 原图第 y-3 行第 X-12 列；最上 6 行、最左 12 列为黑。模式 0 原图不移位。
统计：第二级每拍最左像素（x>=2, y>=4），每帧第一拍时用上一帧统计更新参数，每帧最多变 1~2。
"""
import sys
import numpy as np

W, H = 1280, 720
GRP = W // 4
NS = (GRP - 2) * (H - 4)                  # 每帧统计样本数（与 RTL localparam 一致）


def set_size(w, h):
    global W, H, GRP, NS
    W, H = w, h; GRP = W // 4; NS = (GRP - 2) * (H - 4)


DZ = 4
G_MIN, G_MAX = 8, 24          # 饱和度增益 g/8：1.0 ~ 3.0
S_LO, S_HI = 16, 20            # 目标：最左像素 |cr'|+|cb'| 的平均在 16~20（即平均色差约 9）
NEAR = 24
OMAX = 48
GMAXO = 20                     # 偏色梯度范围 ±20
P0 = dict(t=[42, 84, 126, 168, 210], th=100, phi=128, ocr=0, ocb=0, xcr=0, xcb=0, ycr=0, ycb=0, g=14)


def offmap(o, gx, gy, xb, yy):
    """偏色平面：o + gx*(拍号-GRP/2)/128 + gy*(行号-H/2)/256（每拍 4 个像素共用）"""
    return o + ((gx * (xb - GRP // 2)) >> 7) + ((gy * (yy - H // 2)) >> 8)


def content_xy(shape):
    """第二级中心坐标数组每个像素对应的（第二级输出拍号, 行号）"""
    i, c = np.mgrid[0:shape[0], 0:shape[1]]
    return c // 4 + 2, i + 4


def load_hex(path):
    with open(path) as f:
        rows = [line.strip() for line in f if line.strip()]
    n = len(rows) // (GRP * H)
    assert len(rows) == n * GRP * H, f"{path}: {len(rows)} beats"
    return np.frombuffer(bytes.fromhex("".join(rows)), np.uint8).reshape(n, H, W, 3)


def save_hex(img, path):
    with open(path, "w") as f:
        for beat in img.reshape(H * GRP, 12):
            f.write(beat.tobytes().hex() + "\n")


def lpad(a):
    return np.concatenate([a[:, :1], a], axis=1)


def gray(c):
    return (c[..., 0] + 2 * c[..., 1] + c[..., 2]) >> 2


def core(img):
    """第二级中心坐标（原图行 2..H-3、列 0..W-9）上的 (B2, Y2, mag)"""
    I = img.astype(np.int64)
    P = lpad(I)
    v = P[0:H-2] + 2 * P[1:H-1] + P[2:H]
    B = (v[:, 0:W-1] + 2 * v[:, 1:W] + v[:, 2:W+1]) >> 4       # 行 1..H-2，列 0..W-2
    T, M, Bo = slice(0, H-4), slice(1, H-3), slice(2, H-2)
    NC = W - 8
    col = lambda a, rows, dx: a[rows, 1 + dx: 1 + dx + NC]
    g = gray(B); gp = lpad(g)
    vs = lambda dx: col(gp, T, dx) + 2 * col(gp, M, dx) + col(gp, Bo, dx)
    vd = lambda dx: col(gp, T, dx) - col(gp, Bo, dx)
    mag = np.minimum(np.abs(vs(1) - vs(-1)) + np.abs(vd(-1) + 2 * vd(0) + vd(1)), 255)
    Bp = lpad(B)
    vB = lambda dx: col(Bp, T, dx) + 2 * col(Bp, M, dx) + col(Bp, Bo, dx)
    B2 = (vB(-1) + 2 * vB(0) + vB(1)) >> 4
    return B2, gray(B2), mag


def tones(t):
    e = [0] + list(t) + [255]
    return [(e[k] + e[k + 1]) >> 1 for k in range(6)]


def gain16(d):
    i = d >> 3
    return int(round(255 * 16 / (i * 8 + 4)))


def chroma(c, o, g):
    c = c - o
    a = np.maximum(np.abs(c) - DZ, 0)
    a = np.minimum((a * g) >> 3, 255)
    return np.where(c < 0, -a, a)


def stage2(B2, Y2, mag, mode, p):
    """第二级输出（第三级窗口的输入）：卡通 (band, edge, cr', cb')；素描 gray"""
    if mode == 2:
        floor = p['phi'] >> 3
        d = np.maximum(mag - floor, 0)
        ink = np.minimum((d * gain16(p['phi'] - floor)) >> 4, 255)
        paper = 255 - ((255 - Y2) >> 3)
        return np.maximum(paper - ink, 0)
    t = p['t']
    band = sum((Y2 > ti).astype(np.int64) for ti in t)
    edge = mag >= p['th']
    xb, yy = content_xy(Y2.shape)
    cr = chroma(B2[..., 0] - Y2, offmap(p['ocr'], p['xcr'], p['ycr'], xb, yy), p['g'])
    cb = chroma(B2[..., 2] - Y2, offmap(p['ocb'], p['xcb'], p['ycb'], xb, yy), p['g'])
    return band, edge, cr, cb


def stage3(s2, mode, p):
    """第三级：在第二级结果上做 3x3 窗口；返回原图行 3..H-4、列 0..W-13 的输出"""
    R, NC = H - 6, W - 12
    def win(a, dy, dx):          # a 的坐标：行 = 原图 2..H-3，列 = 原图 0..W-9
        ap = lpad(a)
        return ap[1 + dy: 1 + dy + R, 1 + dx: 1 + dx + NC]
    if mode == 2:
        s = win(s2, 0, 0)
        return np.repeat(s[..., None], 3, -1)
    band, edge, cr, cb = s2
    nb = [win(band, dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
    med = sum(((sum((b <= v).astype(np.int64) for b in nb)) < 5).astype(np.int64) for v in range(5))
    tq = np.array(tones(p['t']))[med]
    c_r, c_b = win(cr, 0, 0), win(cb, 0, 0)
    Rr = tq + c_r; Bb = tq + c_b; G = tq - ((c_r + c_b) >> 1)
    fill = np.clip(np.stack([Rr, G, Bb], -1), 0, 255)
    return np.where(win(edge, 0, 0)[..., None], 0, fill)


def render(B2, Y2, mag, mode, p, img):
    if mode not in (1, 2):
        return img.astype(np.uint8)
    out = np.zeros((H, W, 3), np.int64)
    out[6:H, 12:W] = stage3(stage2(B2, Y2, mag, mode, p), mode, p)
    return out.astype(np.uint8)


def update(p, B2, Y2, mag):
    """用一帧的统计更新参数（每拍最左像素 = 第二级中心列 0,4,8,...）"""
    sel = lambda a: a[:, 0::4][:, :GRP - 2].ravel()
    y, m = sel(Y2), sel(mag)
    crr, cbr = sel(B2[..., 0] - Y2), sel(B2[..., 2] - Y2)
    assert y.size == NS
    t0 = p['t']; t = list(t0); q = [NS * i // 6 for i in range(1, 6)]; tol = NS >> 6
    for i in range(5):
        c = int((y <= t0[i]).sum())
        lo = t0[i - 1] + 4 if i > 0 else 4
        hi = t0[i + 1] - 4 if i < 4 else 251
        if c > q[i] + tol: t[i] = max(t[i] - 2, lo)
        elif c < q[i] - tol: t[i] = min(t[i] + 2, hi)
    ce = int((m >= p['th']).sum()); th = p['th']
    if ce > NS * 9 // 100: th = min(th + 2, 160)
    elif ce < NS * 5 // 100: th = max(th - 2, 16)
    cp = int((m >= p['phi']).sum()); phi = p['phi']
    if cp > NS * 4 // 100: phi = min(phi + 2, 255)
    elif cp < NS * 2 // 100: phi = max(phi - 2, 48)
    xb, yy = sel(content_xy(Y2.shape)[0]), sel(content_xy(Y2.shape)[1])
    # 偏色平面：近中性像素（去偏色后 |cr|,|cb| < 24）中，色差为正和为负的个数比较；
    #   全画面 -> 常数项，右半减左半 -> 水平梯度，下半减上半 -> 垂直梯度
    ofr = offmap(p['ocr'], p['xcr'], p['ycr'], xb, yy)
    ofb = offmap(p['ocb'], p['xcb'], p['ycb'], xb, yy)
    dcr, dcb = crr - ofr, cbr - ofb
    near = (np.abs(dcr) < NEAR) & (np.abs(dcb) < NEAR)
    tolc = NS >> 7
    right, bottom = xb >= GRP // 2, yy >= H // 2
    def bal(d, m):
        return int((near & m & (d > 0)).sum()) - int((near & m & (d < 0)).sum())
    def step(v, b, lim):
        if b > tolc: return min(v + 1, lim)
        if b < -tolc: return max(v - 1, -lim)
        return v
    o = {}
    for ch, d in (('cr', dcr), ('cb', dcb)):
        allm = np.ones_like(right)
        o['o' + ch] = step(p['o' + ch], bal(d, allm), OMAX)
        o['x' + ch] = step(p['x' + ch], bal(d, right) - bal(d, ~right), GMAXO)
        o['y' + ch] = step(p['y' + ch], bal(d, bottom) - bal(d, ~bottom), GMAXO)
    # 饱和度：本帧（用本帧的偏色、g）处理后 |cr'|+|cb'| 的总和与目标比较
    sc = int((np.abs(chroma(crr, ofr, p['g'])) + np.abs(chroma(cbr, ofb, p['g']))).sum())
    g = p['g']
    if sc > NS * S_HI: g = max(g - 1, G_MIN)
    elif sc < NS * S_LO: g = min(g + 1, G_MAX)
    return dict(t=t, th=th, phi=phi, g=g, **o)


def run(img, mode, frames):
    B2, Y2, mag = core(img)
    p = dict(P0); outs = []
    for f in range(frames):
        outs.append((render(B2, Y2, mag, mode, p, img), dict(p)))
        p = update(p, B2, Y2, mag)
    return outs


def converge(img, frames=200):
    B2, Y2, mag = core(img); p = dict(P0)
    for _ in range(frames):
        p = update(p, B2, Y2, mag)
    return B2, Y2, mag, p


def main():
    cmd = sys.argv[1]
    if cmd == "prep":
        if len(sys.argv) > 4: set_size(int(sys.argv[4]), int(sys.argv[5]))
        save_hex(np.fromfile(sys.argv[2], np.uint8).reshape(H, W, 3), sys.argv[3])
    elif cmd == "check":
        if len(sys.argv) > 8: set_size(int(sys.argv[7]), int(sys.argv[8]))
        img = load_hex(sys.argv[2])[0]; rtl = load_hex(sys.argv[3])
        mode, frames = int(sys.argv[4]), int(sys.argv[5])
        exp = run(img, mode, frames)
        assert len(rtl) == frames, f"RTL frames {len(rtl)} != {frames}"
        rtl[-1].tofile(sys.argv[6])
        bad = 0
        for f in range(frames):
            diff = np.any(rtl[f] != exp[f][0], axis=-1); n = int(diff.sum())
            if n:
                ys, xs = np.nonzero(diff); bad += 1
                print(f"MODEL_MISMATCH mode={mode} frame={f}: {n} px, first (y={ys[0]},x={xs[0]}) "
                      f"rtl={rtl[f][ys[0], xs[0]]} exp={exp[f][0][ys[0], xs[0]]} params={exp[f][1]}")
        if bad == 0:
            print(f"MODEL_MATCH mode={mode}: {frames} frames x {W*H} px identical, params {exp[-1][1]}")
        else:
            sys.exit(1)
    elif cmd == "demo":
        img = np.fromfile(sys.argv[2], np.uint8).reshape(H, W, 3)
        B2, Y2, mag, p = converge(img)
        print('converged params', p)
        for m in (1, 2):
            render(B2, Y2, mag, m, p, img).tofile(f"{sys.argv[3]}_m{m}.raw")


if __name__ == "__main__":
    main()
