import re


def modify_geometry_scenario(base_geom_path, out_path, ds_station, us_station, sed_depth, n_value):
    with open(base_geom_path, 'r') as f:
        content = f.read()

    TYPE_RM = 'Type RM Length L Ch R ='
    parts = content.split(TYPE_RM)
    out_parts = [parts[0]]

    for block in parts[1:]:
        lines = block.split('\n')
        first_line = lines[0]

        try:
            fields = first_line.split(',')
            node_type = int(fields[0].strip())
            rs_str = re.sub(r'[^\d.\-]', '', fields[1].strip())
            rs = float(rs_str)
            is_structure = node_type != 1

        except (IndexError, ValueError):
            out_parts.append(TYPE_RM + block)
            continue

        in_reach = ds_station <= rs <= us_station

        if is_structure or not in_reach:
            out_parts.append(TYPE_RM + block)
            continue

        block_lines = block.split('\n')
        out_block_lines = []

        sta_elev_values = []
        reading_sta_elev = False
        n_sta_elev_points = 0
        points_read = 0
        bank_sta_line_idx = None

        j = 0
        while j < len(block_lines):
            current = block_lines[j]

            if current.startswith('#Sta/Elev='):
                reading_sta_elev = True
                try:
                    n_sta_elev_points = int(current.split('=')[1].strip())
                except ValueError:
                    n_sta_elev_points = 0
                out_block_lines.append(current)
                j += 1
                continue

            if reading_sta_elev and points_read < n_sta_elev_points:
                raw = current.rstrip('\r\n')
                values = []
                for k in range(0, len(raw), 8):
                    field = raw[k:k+8].strip()
                    if field:
                        try:
                            values.append(float(field))
                        except ValueError:
                            pass
                for k in range(1, len(values), 2):
                    sta_elev_values.append(values[k])
                points_read += len(values) // 2
                if points_read >= n_sta_elev_points:
                    reading_sta_elev = False
                out_block_lines.append(current)
                j += 1
                continue

            if current.startswith('#Mann=') and in_reach:
                try:
                    after_eq = current.split('=')[1]
                    n_count = int(after_eq.split(',')[0].strip())
                except (IndexError, ValueError):
                    n_count = 1

                out_block_lines.append(current)
                j += 1

                mann_data_lines = []
                chars_needed = n_count * 3 * 8
                chars_collected = 0

                while j < len(block_lines) and chars_collected < chars_needed:
                    mann_line = block_lines[j]
                    mann_stripped = mann_line.strip()

                    if mann_stripped and any(mann_stripped.startswith(k) for k in [
                        '#', 'Bank Sta', 'Levee', 'XS Rating', 'XS HTab',
                        'Exp/Cntr', 'Sediment', 'Permanent', 'BEGIN', 'END',
                        'Node', 'BR ', 'BC ', 'WSPro', 'Blocked', 'Pier', 'Type RM'
                    ]):
                        break

                    if not mann_stripped:
                        j += 1
                        continue

                    mann_data_lines.append(mann_line)
                    chars_collected += len(mann_line.rstrip('\r\n'))
                    j += 1

                raw = ''.join(line.rstrip('\r\n') for line in mann_data_lines)
                result_chars = list(raw)
                for triplet_idx in range(n_count):
                    n_field_start = (triplet_idx * 3 + 1) * 8
                    n_field_end = n_field_start + 8
                    replacement = f'{n_value:8.4f}'
                    result_chars[n_field_start:n_field_end] = list(replacement)

                new_raw = ''.join(result_chars)
                pos = 0
                for line in mann_data_lines:
                    stripped_len = len(line.rstrip('\r\n'))
                    chunk = new_raw[pos:pos + stripped_len]
                    ending = line[stripped_len:]
                    out_block_lines.append(chunk + ending)
                    pos += stripped_len

                continue

            if current.startswith('Bank Sta='):
                bank_sta_line_idx = len(out_block_lines)
                out_block_lines.append(current)
                j += 1
                continue

            if current.startswith('Sediment Elevation='):
                if sta_elev_values:
                    thalweg = min(sta_elev_values)
                    abs_sed_elev = round(thalweg + sed_depth, 4)
                    out_block_lines.append(
                        f'Sediment Elevation={abs_sed_elev}\r\n'
                    )
                j += 1
                continue

            out_block_lines.append(current)
            j += 1

        if bank_sta_line_idx is not None:
            already_has_sed = any(
                l.startswith('Sediment Elevation=')
                for l in out_block_lines[bank_sta_line_idx:]
            )
            if not already_has_sed and sta_elev_values:
                thalweg = min(sta_elev_values)
                abs_sed_elev = round(thalweg + sed_depth, 4)
                out_block_lines.insert(
                    bank_sta_line_idx + 1,
                    f'Sediment Elevation={abs_sed_elev}\r\n'
                )

        out_parts.append(TYPE_RM + '\n'.join(out_block_lines))

    with open(out_path, 'w') as f:
        f.write('\n'.join(out_parts) if len(out_parts) > 1 else out_parts[0])

    print(f"    Scenario geometry written to: {out_path}")


def set_geom_title(geom_path, title):
    with open(geom_path, 'r') as f:
        lines = f.readlines()

    for idx, line in enumerate(lines):
        if line.startswith('Geom Title='):
            lines[idx] = f'Geom Title={title}\r\n'
            break

    with open(geom_path, 'w') as f:
        f.writelines(lines)

    print(f"    Geom Title set to: {title}")