"""
MRI 데이터셋 중복 파일 검사 스크립트

사용법:
    python check_duplicates.py                 # archive/ 폴더 검사
    python check_duplicates.py <경로>          # 원하는 폴더 검사
    python check_duplicates.py <경로> --delete # 중복본 삭제(먼저 목록 확인 후 사용)
"""

import hashlib
import sys
from collections import defaultdict
from pathlib import Path

CHUNK = 1024 * 1024  # 1MB


def file_hash(path: Path) -> str:
    """파일 내용의 MD5 해시 (내용이 같으면 이름이 달라도 같은 값)."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def scan(root: Path):
    """폴더를 훑어 (전체 파일 목록, 해시 -> 파일목록) 반환."""
    files = [p for p in root.rglob("*") if p.is_file()]

    # 1단계: 크기로 후보 추리기 (해시 계산 비용 절감)
    by_size = defaultdict(list)
    for p in files:
        by_size[p.stat().st_size].append(p)

    # 2단계: 크기가 같은 것들만 해시 비교
    by_hash = defaultdict(list)
    for size, group in by_size.items():
        if len(group) < 2:
            continue
        for p in group:
            by_hash[file_hash(p)].append(p)

    return files, by_hash


def top_level_summary(root: Path):
    """최상위 하위 폴더별 파일 수 요약."""
    print(f"\n[폴더별 파일 수] {root}")
    total = 0
    for child in sorted(root.iterdir()):
        if child.is_dir():
            n = sum(1 for p in child.rglob("*") if p.is_file())
            print(f"  {child.name:40s} {n:>8,} 개")
            total += n
        else:
            total += 1
    print(f"  {'(최상위 파일 포함) 합계':40s} {total:>8,} 개")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_delete = "--delete" in sys.argv

    root = Path(args[0]) if args else Path(__file__).parent / "archive"
    root = root.resolve()

    if not root.exists():
        print(f"경로를 찾을 수 없습니다: {root}")
        return

    print("=" * 70)
    print(f"검사 대상: {root}")
    print("=" * 70)

    top_level_summary(root)

    files, by_hash = scan(root)

    dup_groups = {h: ps for h, ps in by_hash.items() if len(ps) > 1}
    dup_extra = sum(len(ps) - 1 for ps in dup_groups.values())          # 지워도 되는 개수
    dup_bytes = sum(ps[0].stat().st_size * (len(ps) - 1) for ps in dup_groups.values())

    print("\n" + "=" * 70)
    print("[중복 요약]")
    print(f"  전체 파일 수        : {len(files):,} 개")
    print(f"  고유 파일 수        : {len(files) - dup_extra:,} 개")
    print(f"  중복 그룹 수        : {len(dup_groups):,} 개")
    print(f"  중복(여분) 파일 수  : {dup_extra:,} 개")
    print(f"  중복이 차지한 용량  : {dup_bytes / 1024 / 1024:,.1f} MB")
    print("=" * 70)

    # 어떤 폴더 쌍에서 중복이 많이 나는지 집계
    pair_count = defaultdict(int)
    for ps in dup_groups.values():
        tops = sorted({p.relative_to(root).parts[0] for p in ps})
        pair_count[" <-> ".join(tops)] += 1

    print("\n[중복이 발생한 폴더 조합]")
    for pair, n in sorted(pair_count.items(), key=lambda x: -x[1]):
        print(f"  {pair:50s} {n:>8,} 그룹")

    print("\n[중복 예시 5건]")
    for ps in list(dup_groups.values())[:5]:
        print("  - " + "\n    ".join(str(p.relative_to(root)) for p in ps))

    if do_delete:
        # 경로가 가장 짧은(=상위) 파일 1개만 남기고 나머지 삭제
        removed = 0
        for ps in dup_groups.values():
            keep = min(ps, key=lambda p: (len(p.parts), str(p)))
            for p in ps:
                if p != keep:
                    p.unlink()
                    removed += 1
        print(f"\n삭제 완료: {removed:,} 개 파일 제거")
    elif dup_extra:
        print("\n삭제하려면:  python check_duplicates.py "
              f'"{root}" --delete   (원본 1개는 남깁니다)')


if __name__ == "__main__":
    main()
