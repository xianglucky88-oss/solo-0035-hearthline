import csv
import io


def as_csv(dispatch):
    output = io.StringIO(newline='')
    writer = csv.writer(output, lineterminator='\r\n')
    writer.writerow(['炉次', '料盘', '炉区', '炉位', '开始秒', '结束秒', '有证秒', '最长连续达标秒', '交接摘要'])
    for tray in dispatch['included']:
        for stage in tray['stages']:
            writer.writerow([dispatch['run'], tray['id'], stage['zone'], stage['slot'], stage['from'], stage['to'],
                             stage['known_s'], stage['longest_s'], dispatch['dispatch_hash']])
    return output.getvalue().encode('utf-8-sig')
