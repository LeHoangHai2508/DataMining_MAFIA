# mafia.py
from collections import defaultdict

def build_tidsets(transactions):
    """
    Chuyển giao dịch sang dạng bitmap (TID-sets).
    Output: dict {item: set(tid)}
    """
    tidsets = defaultdict(set)
    for tid, transaction in enumerate(transactions):
        for item in transaction:
            tidsets[item].add(tid)
    return tidsets

def mafia(head, tail, tidsets, minsup, MFI, parent_tids):
    """
    Triển khai thuật toán MAFIA theo DFS với pruning.
    head: tập mục hiện tại (set)
    tail: danh sách item mở rộng
    tidsets: dict item -> set(tid)
    minsup: ngưỡng hỗ trợ tối thiểu (int)
    MFI: danh sách kết quả
    parent_tids: giao dịch hiện tại (set)
    """
    # Bước 4: HUT Pruning
    hut = head | set(tail)
    if any(mfi.issuperset(hut) for mfi in MFI):
        return

    frequent_extensions = []
    for item in tail:
        tids_new = tidsets[item] & parent_tids
        if len(tids_new) >= minsup:
            frequent_extensions.append((item, tids_new))

    # Bước 5: Sắp xếp lại động theo support tăng dần
    frequent_extensions.sort(key=lambda x: len(x[1]))

    extended = False
    for i, (item, tids_i) in enumerate(frequent_extensions):
        new_tail = [it for it, _ in frequent_extensions[i+1:]]

        # Bước 3: PEP pruning
        if tids_i == parent_tids:
            continue

        mafia(head | {item}, new_tail, tidsets, minsup, MFI, tids_i)
        extended = True

    # Bước 6: Ghi nhận tập phổ biến cực đại
    if not extended:
        if not any(existing.issuperset(head) for existing in MFI):
            MFI.append(head)

def find_maximal_itemsets(transactions, min_support=0.3):
    """
    Giao diện chính để tìm tập phổ biến cực đại bằng MAFIA
    """
    minsup = int(min_support * len(transactions))
    tidsets = build_tidsets(transactions)
    items = sorted(tidsets.keys())
    all_tids = set(range(len(transactions)))
    MFI = []
    mafia(set(), items, tidsets, minsup, MFI, all_tids)
    return MFI
