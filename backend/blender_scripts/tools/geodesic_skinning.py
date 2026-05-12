"""
Geodesic Skinning Weights
===========================
Mesh vertex'lerine geodesic mesafe tabanli skinning agirliklari atar.

Yontem:
1. Her kemik icin kemige en yakin vertex'leri bul
2. Bu vertex'lerden Dijkstra ile tum vertex'lere geodesic mesafe hesapla
3. Mesafeyi Gaussian kernel ile agirliga donustur
4. Normalize et (her vertex'te toplam = 1.0)
5. Blender vertex group'larina ata

Avantajlar:
- Yuzeyi topolojisine saygi gosterir (gogus kemigi sirt vertex'lerini etkilemez)
- Blender heat map'e alternatif — tam kontrol
- Non-watertight mesh'lerde daha guvenilir
"""

import numpy as np
import heapq
import bpy
from mathutils import Vector

from .config import SKINNING_SIGMA_RATIO, SKINNING_MAX_INFLUENCES, SIDES
from .utils import select_only, build_adjacency


def find_bone_nearest_vertices(verts, rig):
    """
    Her kemik icin mesh'teki en yakin vertex'leri bul.

    Bir kemigin 'influence source' vertex'leri, kemik segmentine
    (head-tail arasi cizgi) en yakin olan vertex'lerdir.

    Args:
        verts: (N, 3) vertex pozisyonlari
        rig: Blender Armature objesi

    Returns:
        bone_sources: dict[str, list[int]] — her kemik icin
            kaynak vertex index'leri
    """
    select_only(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = rig.data.edit_bones
    world = rig.matrix_world

    bone_sources = {}

    for bone in eb:
        head = np.array([*(world @ bone.head)])
        tail = np.array([*(world @ bone.tail)])

        # Her vertex'in kemik segmentine mesafesi
        # Point-to-segment distance
        segment = tail - head
        seg_len = np.linalg.norm(segment)

        if seg_len < 1e-8:
            # Degenerate kemik — nokta olarak isle
            dists = np.linalg.norm(verts - head, axis=1)
        else:
            seg_dir = segment / seg_len
            # Her vertex icin projeksiyon parametresi t
            v_to_head = verts - head
            t = np.dot(v_to_head, seg_dir)
            t = np.clip(t, 0, seg_len)

            # En yakin nokta segment uzerinde
            closest = head + np.outer(t, seg_dir)
            dists = np.linalg.norm(verts - closest, axis=1)

        # En yakin 3-5 vertex'i source olarak sec
        n_sources = min(5, len(verts))
        source_indices = np.argsort(dists)[:n_sources].tolist()
        bone_sources[bone.name] = source_indices

    bpy.ops.object.mode_set(mode='OBJECT')
    return bone_sources


def compute_geodesic_weights(verts, edges, bone_sources, sigma=None):
    """
    Her kemik icin geodesic mesafe tabanli agirliklar hesapla.

    Adimlar:
    1. Her kemik'in source vertex'lerinden multi-source Dijkstra
    2. Mesafe → agirlik: w = exp(-d^2 / (2*sigma^2))
    3. Tum kemikler icin normalize: sum(w_i) = 1 per vertex

    Args:
        verts: (N, 3) vertex pozisyonlari
        edges: (E, 2) edge index'leri
        bone_sources: dict[str, list[int]] — kemik source vertex'leri
        sigma: float — Gaussian kernel genisligi

    Returns:
        weights: dict[str, np.array] — her kemik icin (N,) agirlik array
    """
    n_verts = len(verts)

    if sigma is None:
        z_range = verts[:, 2].max() - verts[:, 2].min()
        sigma = z_range * SKINNING_SIGMA_RATIO

    adj = build_adjacency(n_verts, edges)

    bone_distances = {}

    print(f"   [SKINNING] {len(bone_sources)} kemik icin "
          f"geodesic mesafe hesaplanıyor (sigma={sigma:.4f})...")

    for bone_name, sources in bone_sources.items():
        # Multi-source Dijkstra
        dist = np.full(n_verts, np.inf)
        heap = []
        visited = np.zeros(n_verts, dtype=bool)

        for src in sources:
            dist[src] = 0.0
            heapq.heappush(heap, (0.0, src))

        while heap:
            d, u = heapq.heappop(heap)
            if visited[u]:
                continue
            visited[u] = True

            for v in adj[u]:
                if visited[v]:
                    continue
                edge_len = np.linalg.norm(verts[u] - verts[v])
                new_dist = d + edge_len
                if new_dist < dist[v]:
                    dist[v] = new_dist
                    heapq.heappush(heap, (new_dist, v))

        bone_distances[bone_name] = dist

    # Mesafe → agirlik (Gaussian kernel)
    raw_weights = {}
    for bone_name, dist in bone_distances.items():
        w = np.exp(-dist ** 2 / (2 * sigma ** 2))
        w[np.isinf(dist)] = 0.0
        raw_weights[bone_name] = w

    # Normalize: her vertex'te toplam = 1.0
    weight_sum = np.zeros(n_verts)
    for w in raw_weights.values():
        weight_sum += w

    weight_sum = np.maximum(weight_sum, 1e-10)

    weights = {}
    for bone_name, w in raw_weights.items():
        weights[bone_name] = w / weight_sum

    return weights


def prune_weights(weights, max_influences=None):
    """
    Her vertex'te en fazla max_influences kemik etkisi birak.

    Kucuk agirliklar sifirlanir, kalanlar yeniden normalize edilir.
    Bu, deformasyon performansini arttirir ve artefaktlari azaltir.

    Args:
        weights: dict[str, np.array] — ham agirliklar
        max_influences: int — vertex basina max kemik sayisi

    Returns:
        pruned: dict[str, np.array] — budanmis agirliklar
    """
    if max_influences is None:
        max_influences = SKINNING_MAX_INFLUENCES

    bone_names = list(weights.keys())
    n_verts = len(next(iter(weights.values())))

    # Tum agirliklari matrise cevir (N x B)
    weight_matrix = np.zeros((n_verts, len(bone_names)))
    for bi, name in enumerate(bone_names):
        weight_matrix[:, bi] = weights[name]

    # Her vertex icin en buyuk max_influences agirlik disindakileri sifirla
    for vi in range(n_verts):
        row = weight_matrix[vi]
        if (row > 0).sum() <= max_influences:
            continue

        # En buyuk max_influences index'i bul
        top_indices = np.argsort(row)[-max_influences:]
        mask = np.zeros(len(bone_names), dtype=bool)
        mask[top_indices] = True
        row[~mask] = 0.0

        # Yeniden normalize
        total = row.sum()
        if total > 1e-10:
            row /= total

    # Dict'e geri donustur
    pruned = {}
    for bi, name in enumerate(bone_names):
        pruned[name] = weight_matrix[:, bi]

    return pruned


def assign_weights_to_mesh(mesh_obj, rig, weights):
    """
    Hesaplanan agirliklari Blender vertex group'larina ata.

    Mevcut vertex group'lari temizler ve yeni agirliklar yazar.
    Sonra mesh'i armature'a parent eder (ARMATURE_NAME ile).

    Args:
        mesh_obj: Blender mesh objesi
        rig: Blender Armature objesi
        weights: dict[str, np.array] — kemik agirliklari
    """
    print("[SKINNING] Agirliklar Blender vertex group'larina atanıyor...")

    # Mevcut vertex group'lari temizle
    mesh_obj.vertex_groups.clear()

    # Her kemik icin vertex group olustur
    for bone_name, w in weights.items():
        vg = mesh_obj.vertex_groups.new(name=bone_name)

        # Sifir olmayan agirliklari ata
        nonzero = np.where(w > 1e-6)[0]
        for vi in nonzero:
            vg.add([int(vi)], float(w[vi]), 'REPLACE')

    print(f"   [SKINNING] {len(weights)} vertex group oluşturuldu")

    # Mesh'i armature'a parent et
    select_only(mesh_obj)
    mesh_obj.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig

    try:
        bpy.ops.object.parent_set(type='ARMATURE_NAME')
        print("   [SKINNING] Mesh armature'a parent edildi (ARMATURE_NAME)")
    except Exception as e:
        print(f"   [SKINNING] UYARI: Parent set başarısız: {e}")
        # Manuel parent
        mesh_obj.parent = rig
        mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
        mod.object = rig
        print("   [SKINNING] Manuel parent + armature modifier eklendi")


def compute_and_assign_skinning(mesh_obj, rig, verts, edges):
    """
    Tam skinning pipeline'ı.

    1. Kemik source vertex'leri bul
    2. Geodesic agirliklar hesapla
    3. Agirlik budama (max 4 influence)
    4. Blender vertex group'larina ata

    Args:
        mesh_obj: Blender mesh objesi
        rig: Blender Armature objesi
        verts: (N, 3) vertex pozisyonlari
        edges: (E, 2) edge index'leri
    """
    print("[SKINNING] Geodesic skinning weights hesaplanıyor...")

    # 1. Kemik source vertex'leri
    bone_sources = find_bone_nearest_vertices(verts, rig)
    print(f"   [SKINNING] {len(bone_sources)} kemik icin source vertex'ler bulundu")

    # 2. Geodesic agirliklar
    weights = compute_geodesic_weights(verts, edges, bone_sources)

    # 3. Budama
    weights = prune_weights(weights)

    # 4. Blender'a ata
    assign_weights_to_mesh(mesh_obj, rig, weights)

    print("[SKINNING] Tamamlandı")


"""
Geodesic Extrema
=================
Mesh yuzeyindeki geodesic mesafeleri hesaplayarak
uzuv uclarini (bas, eller, ayaklar) tespit eder.

Yontem:
1. Rastgele bir vertex'ten Dijkstra → en uzak vertex (A)
2. A'dan Dijkstra → en uzak vertex (B) → A-B = mesh capi
3. A'dan tum vertex'lere mesafe → lokal maksimumlar = uzuv uclari

Insansi mesh'te bu her zaman {bas, sol_ayak, sag_ayak, sol_el, sag_el}
verir. Hicbir heuristic GEREKMEZ, Z ekseni varsayimi YOK.
"""

import numpy as np
import heapq
from .utils import build_adjacency
from .config import NUM_EXTREMA


def dijkstra_geodesic(verts, adj, source):
    """
    Tek kaynaktan tum vertex'lere geodesic mesafe (Dijkstra).

    Mesh edge'leri uzerinde Euclidean mesafeyi kullanir.
    Heat method'dan daha yavas ama daha basit ve guvenilir.

    Args:
        verts: (N, 3) vertex pozisyonlari
        adj: Adjacency list (build_adjacency'den)
        source: Kaynak vertex index'i

    Returns:
        dist: (N,) array — her vertex'e geodesic mesafe
    """
    n = len(verts)
    dist = np.full(n, np.inf)
    dist[source] = 0.0

    # Min-heap: (mesafe, vertex_index)
    heap = [(0.0, source)]
    visited = np.zeros(n, dtype=bool)

    while heap:
        d, u = heapq.heappop(heap)
        if visited[u]:
            continue
        visited[u] = True

        for v in adj[u]:
            if visited[v]:
                continue
            edge_len = np.linalg.norm(verts[u] - verts[v])
            new_dist = d + edge_len
            if new_dist < dist[v]:
                dist[v] = new_dist
                heapq.heappush(heap, (new_dist, v))

    return dist


def find_diameter_endpoints(verts, adj):
    """
    Mesh'in geodesic capinin iki ucunu bul.

    Algoritma:
    1. Rastgele vertex'ten baslayarak en uzak noktayi bul (A)
    2. A'dan en uzak noktayi bul (B)
    3. A-B = yaklasik geodesic cap

    Insansi mesh'te A-B genellikle bas-ayak veya ayak-ayak olur.

    Returns:
        endpoint_a: int — ilk uc vertex index'i
        endpoint_b: int — ikinci uc vertex index'i
        dist_a: (N,) — A'dan tum vertex'lere mesafe
        dist_b: (N,) — B'den tum vertex'lere mesafe
    """
    n = len(verts)
    # Rastgele baslangic (mesh merkezine en yakin vertex)
    center = verts.mean(axis=0)
    start = np.argmin(np.linalg.norm(verts - center, axis=1))

    # 1. Adim: start'tan en uzak = endpoint_a
    dist_start = dijkstra_geodesic(verts, adj, start)
    endpoint_a = int(np.argmax(dist_start))

    # 2. Adim: endpoint_a'dan en uzak = endpoint_b
    dist_a = dijkstra_geodesic(verts, adj, endpoint_a)
    endpoint_b = int(np.argmax(dist_a))

    # 3. Adim: endpoint_b'den de mesafeleri hesapla
    dist_b = dijkstra_geodesic(verts, adj, endpoint_b)

    diameter = dist_a[endpoint_b]
    print(f"   [GEODESIC] Mesh capi: {diameter:.4f} "
          f"(A={endpoint_a}, B={endpoint_b})")

    return endpoint_a, endpoint_b, dist_a, dist_b


def find_geodesic_extrema(verts, adj, dist_from_source, num_extrema=None):
    """
    Geodesic mesafe alanindaki lokal maksimumlari bul.

    Her lokal maksimum bir uzuv ucuna karsilik gelir.
    Insansi mesh'te 5 extremum beklenir:
    - Bas (zaten diameter endpoint olabilir)
    - Sol el, sag el
    - Sol ayak, sag ayak

    Args:
        verts: (N, 3) vertex pozisyonlari
        adj: Adjacency list
        dist_from_source: (N,) — bir ayak noktasindan mesafeler
        num_extrema: Beklenen extremum sayisi

    Returns:
        extrema: list[(vertex_idx, distance)] — sirali extremum'lar
    """
    if num_extrema is None:
        num_extrema = NUM_EXTREMA

    n = len(verts)

    # Her vertex icin komsularindan daha uzak mi?
    is_local_max = np.zeros(n, dtype=bool)

    for i in range(n):
        if not adj[i]:  # Izole vertex
            continue
        d = dist_from_source[i]
        if np.isinf(d):
            continue
        # Tum komsulardan buyuk veya esit mi?
        is_max = True
        for j in adj[i]:
            if dist_from_source[j] > d:
                is_max = False
                break
        is_local_max[i] = is_max

    # Lokal maksimumlari mesafeye gore sirala
    max_indices = np.where(is_local_max)[0]
    max_distances = dist_from_source[max_indices]
    sorted_order = np.argsort(max_distances)[::-1]

    # En yuksek extremum'lari sec (cok yakin olanlari eleme)
    extrema = []
    min_separation = dist_from_source.max() * 0.15

    for idx in sorted_order:
        vi = int(max_indices[idx])
        d = float(max_distances[idx])

        # Onceki extremum'lara cok yakin mi?
        too_close = False
        for prev_vi, _ in extrema:
            sep = np.linalg.norm(verts[vi] - verts[prev_vi])
            if sep < min_separation:
                too_close = True
                break

        if not too_close:
            extrema.append((vi, d))
            if len(extrema) >= num_extrema * 2:
                break

    # En uzak num_extrema'yi sec
    extrema = extrema[:num_extrema]

    return extrema


def classify_extrema(verts, extrema):
    """
    Geodesic extremum'lari anatomik olarak siniflandir.

    Siniflandirma Z ve X koordinatlarina gore:
    - En yuksek Z → bas
    - En dusuk Z (2 tane) → sol/sag ayak
    - Kalan (2 tane) → sol/sag el

    Returns:
        landmarks: dict — siniflandirilmis uzuv uclari
    """
    if not extrema:
        return {}

    positions = np.array([verts[vi] for vi, _ in extrema])
    indices = [vi for vi, _ in extrema]
    distances = [d for _, d in extrema]

    z_vals = positions[:, 2]
    x_vals = positions[:, 0]

    landmarks = {}

    # En yuksek Z → bas
    head_idx = np.argmax(z_vals)
    landmarks["head_geodesic"] = {
        "position": positions[head_idx],
        "vertex_idx": indices[head_idx],
        "confidence": 0.85,
        "source": "geodesic",
    }

    # Kalan vertex'lerden en dusuk Z (2 tane) → ayaklar
    remaining = list(range(len(extrema)))
    remaining.remove(head_idx)

    if len(remaining) >= 2:
        remaining_z = [(i, z_vals[i]) for i in remaining]
        remaining_z.sort(key=lambda x: x[1])

        foot_indices = [remaining_z[0][0], remaining_z[1][0]]

        # Sol/sag ayirimi: X koordinatina gore
        x_center = np.median(x_vals)
        for fi in foot_indices:
            side = "l" if positions[fi, 0] > x_center else "r"
            landmarks[f"foot_{side}_geodesic"] = {
                "position": positions[fi],
                "vertex_idx": indices[fi],
                "confidence": 0.80,
                "source": "geodesic",
            }

        # Kalan → eller
        hand_remaining = [i for i in remaining if i not in foot_indices]
        for hi in hand_remaining[:2]:
            side = "l" if positions[hi, 0] > x_center else "r"
            landmarks[f"hand_{side}_geodesic"] = {
                "position": positions[hi],
                "vertex_idx": indices[hi],
                "confidence": 0.75,
                "source": "geodesic",
            }

    elif len(remaining) >= 1:
        # Sadece 1 kaldi — en dusuk Z = ayak
        fi = remaining[0]
        landmarks["foot_geodesic"] = {
            "position": positions[fi],
            "vertex_idx": indices[fi],
            "confidence": 0.60,
            "source": "geodesic",
        }

    return landmarks


def analyze_geodesic(verts, edges):
    """
    Tam geodesic extrema pipeline'ı.

    Returns:
        landmarks: dict — siniflandirilmis uzuv uclari
        geodesic_data: dict — mesafe alanlari (debug icin)
    """
    print("[GEODESIC] Geodesic extrema hesaplanıyor...")

    adj = build_adjacency(len(verts), edges)

    # 1. Mesh capinin iki ucunu bul
    ep_a, ep_b, dist_a, dist_b = find_diameter_endpoints(verts, adj)

    # 2. Daha alçak endpoint'ten (ayak) tum vertex'lere mesafe
    if verts[ep_a, 2] < verts[ep_b, 2]:
        foot_idx = ep_a
        dist_from_foot = dist_a
    else:
        foot_idx = ep_b
        dist_from_foot = dist_b

    # 3. Lokal maksimumlari bul = uzuv uclari
    extrema = find_geodesic_extrema(verts, adj, dist_from_foot)
    print(f"   [GEODESIC] Extrema: {len(extrema)} nokta bulundu")

    # 4. Anatomik siniflandirma
    landmarks = classify_extrema(verts, extrema)

    geodesic_data = {
        "dist_a": dist_a,
        "dist_b": dist_b,
        "endpoint_a": ep_a,
        "endpoint_b": ep_b,
        "extrema": extrema,
    }

    print(f"[GEODESIC] Tamamlandı — {len(landmarks)} landmark tespit edildi")
    return landmarks, geodesic_data
