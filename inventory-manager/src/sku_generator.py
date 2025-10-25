# sku_generator.py
class SKUGenerator:
    def __init__(self, max_length=30):
        self.max_length = max_length

    def generate(self, title, category):
        """
        Generate SKU from title and category.

        If title is in format [a] - [b], SKU becomes truncated a + truncated b + truncated category.
        Max total length = self.max_length, no padding.
        """
        title = title.strip()
        category = category.strip().upper().replace(" ", "")
        a, b = "", ""

        if " - " in title:
            parts = title.split(" - ", 1)
            a, b = parts[0].upper().replace(" ", ""), parts[1].upper().replace(" ", "")
        else:
            # Fallback: use full title
            a, b = title.upper().replace(" ", ""), ""

        # Allocate characters proportionally
        # Leave room for two hyphens
        remaining = self.max_length - 2
        if a and b:
            max_len_a = remaining // 2
            max_len_b = remaining - max_len_a
            a_trunc = a[:max_len_a]
            b_trunc = b[:max_len_b]
        else:
            # Only one part
            a_trunc = a[:remaining]
            b_trunc = ""

        # Truncate category if needed
        cat_len = self.max_length - len(a_trunc) - len(b_trunc) - (1 if b_trunc else 0)
        cat_trunc = category[:cat_len]

        if b_trunc:
            sku = f"{a_trunc}-{b_trunc}-{cat_trunc}"
        else:
            sku = f"{a_trunc}-{cat_trunc}"

        return sku
