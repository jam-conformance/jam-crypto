"""Reed-Solomon erasure coding with Lagrange interpolation.

The shards are byte for byte the shards of the reed-solomon-simd crate
(version 3.1.0). test_compat.py checks this against the crate.
"""

POLYNOMIAL = 0x1002D  # x^16 + x^5 + x^3 + x^2 + 1
CANTOR_BASIS = [
    0x0001, 0xACCA, 0x3C0E, 0x163E, 0xC582, 0xED2E, 0x914C, 0x4012,
    0x6C98, 0x10D8, 0x6A72, 0xB900, 0xFDB8, 0xFB34, 0xFF38, 0x991E,
]


def from_cantor(element):
    polynomial = 0
    for bit, basis_element in enumerate(CANTOR_BASIS):
        if element >> bit & 1:
            polynomial ^= basis_element
    return polynomial


TO_CANTOR = [0] * 65536
for element in range(65536):
    TO_CANTOR[from_cantor(element)] = element

EXP = [0] * 65535
LOG = [0] * 65536
power = 1
for exponent in range(65535):
    EXP[exponent] = TO_CANTOR[power]
    LOG[TO_CANTOR[power]] = exponent
    power <<= 1
    if power & 0x10000:
        power ^= POLYNOMIAL


def mul(left, right):
    if left == 0 or right == 0:
        return 0
    return EXP[(LOG[left] + LOG[right]) % 65535]


def inv(element):
    return EXP[-LOG[element] % 65535]


def lagrange_coefficients(points, target):
    coefficients = []
    for point in points:
        numerator = denominator = 1
        for other in points:
            if other != point:
                numerator = mul(numerator, target ^ other)
                denominator = mul(denominator, point ^ other)
        coefficients.append(mul(numerator, inv(denominator)))
    return coefficients


def sum_of_products(coefficients, values):
    total = 0
    for coefficient, value in zip(coefficients, values):
        total ^= mul(coefficient, value)
    return total


def shard_to_symbols(shard):
    symbols = []
    for start in range(0, len(shard), 64):
        block = shard[start:start + 64]
        half = len(block) // 2
        for low, high in zip(block[:half], block[half:]):
            symbols.append(low | high << 8)
    return symbols


def symbols_to_shard(symbols):
    shard = bytearray()
    for start in range(0, len(symbols), 32):
        block = symbols[start:start + 32]
        shard += bytes(symbol & 0xFF for symbol in block)
        shard += bytes(symbol >> 8 for symbol in block)
    return bytes(shard)


def columns(shards):
    shard_bytes = len(shards[0])
    if shard_bytes == 0 or shard_bytes % 2 != 0:
        raise ValueError("shard size must be even and not zero")
    if any(len(shard) != shard_bytes for shard in shards):
        raise ValueError("shards must have the same size")
    return list(zip(*map(shard_to_symbols, shards)))


def interpolate_shards(points, shards, targets):
    shard_columns = columns(shards)
    result = []
    for target in targets:
        coefficients = lagrange_coefficients(points, target)
        symbols = [sum_of_products(coefficients, column)
                   for column in shard_columns]
        result.append(symbols_to_shard(symbols))
    return result


def next_power_of_two(count):
    power = 1
    while power < count:
        power *= 2
    return power


def code_points(original_count, recovery_count):
    original_pow2 = next_power_of_two(original_count)
    recovery_pow2 = next_power_of_two(recovery_count)
    smaller_pow2 = min(original_pow2, recovery_pow2)
    larger_count = max(original_count, recovery_count)
    too_many = smaller_pow2 + larger_count > 65536
    if original_count == 0 or recovery_count == 0 or too_many:
        raise ValueError("unsupported shard count")

    if original_pow2 > recovery_pow2:
        data_end = recovery_pow2 + original_count
        original = range(recovery_pow2, data_end)
        recovery = range(recovery_count)
        zeros = range(data_end, next_power_of_two(data_end))
    else:
        original = range(original_count)
        recovery = range(original_pow2, original_pow2 + recovery_count)
        zeros = range(original_count, original_pow2)
    return list(original), list(recovery), list(zeros)


def encode(original_count, recovery_count, original):
    if len(original) != original_count:
        raise ValueError("wrong number of original shards")
    original_points, recovery_points, zero_points = code_points(
        original_count, recovery_count
    )
    zero_shard = bytes(len(original[0]))
    points = original_points + zero_points
    shards = list(original) + [zero_shard] * len(zero_points)
    return interpolate_shards(points, shards, recovery_points)


def decode(original_count, recovery_count, original, recovery):
    original_points, recovery_points, zero_points = code_points(
        original_count, recovery_count
    )
    missing = [index for index in range(original_count)
               if index not in original]
    if not missing:
        return {}
    received = [(original_points[index], shard)
                for index, shard in original.items()]
    received += [(recovery_points[index], shard)
                 for index, shard in recovery.items()]
    if len(received) < original_count:
        raise ValueError("not enough shards")

    received = received[:original_count]
    zero_shard = bytes(len(received[0][1]))
    points = [point for point, _ in received] + zero_points
    shards = [shard for _, shard in received] + [zero_shard] * len(zero_points)
    targets = [original_points[index] for index in missing]
    return dict(zip(missing, interpolate_shards(points, shards, targets)))


if __name__ == "__main__":
    original = [
        b"Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do ",
        b"eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut e",
        b"nim ad minim veniam, quis nostrud exercitation ullamco laboris n",
    ]
    recovery = encode(3, 5, original)
    restored = decode(3, 5, {1: original[1]}, {1: recovery[1], 4: recovery[4]})
    assert restored == {0: original[0], 2: original[2]}
    for shard in recovery:
        print(shard[:16].hex())
