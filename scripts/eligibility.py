"""Article eligibility from public feed signals and prior publication metadata."""
from collections import Counter, defaultdict
import datetime as dt
import re
import unicodedata

from collect import CREATOR_CATEGORY, GROUP_ORDER, creator_focus, norm

REVIEW_WINDOW = dt.timedelta(hours=72)
TOPIC = re.compile(
    r'考察|感想|印象|見立て|振り返|参戦|レポ|批評|レビュー|分析|解説|について|のこと|'
    r'読み解|観た|聴いた|見た|行ってきた|が好き|を好き|思っ|感じた|楽し|面白|'
    r'なぜ|理由|どう|という話|なった話|してほしい|おめでとう|ありがとう|最高|'
    r'自分なり|メモ|気づ|推して|必要な|考え|を読む|所感|ひとこと'
)
ACTIVITY = re.compile(
    r'ライブ|ツアー|アニラ|バスラ|公演|卒業|加入|選抜|センター|セトリ|振付|'
    r'歌詞|楽曲|アルバム|曲評|パフォーマンス|ダンス|衣装|冠番組|個人pv|フォーメーション|'
    r'期生|ミーグリ|ミート[＆&]グリート|配信視聴|写真集|出演|キャプテン|選曲|'
    r'シングル|全ツ|\d+(?:st|nd|rd|th)sg|写真展|結成|トーク会|talkを|\d+人のプリンシパル|'
    r'mv(?![a-z])|(?<![a-z])live(?![a-z])'
)
FAN_CONTEXT = re.compile(
    r'リアルミーグリ|アンダーライブ|アンダラ|選抜発表|backs(?:live)?|'
    r'新参者live|卒セレ|バスラ|アニラ|ひな誕祭|お見立て会|推しメン'
)
NOTICE = re.compile(
    r'みんフォト.{0,8}登録|登録用投稿|pr案件|アフィリエイト(?:広告|リンク)|'
    r'商品紹介|クーポンコード|チケット(?:譲ります|お譲り|求む)|拡散希望.{0,15}販売|'
    r'公式.{0,12}(?:抜粋集|転載)|購入方法.{0,18}(?:特典|まとめ)'
)
INCIDENTAL = re.compile(r'一例として|話が中心|本題ではない|関係ありません|の名前を挙げただけ')
REFERENCE_LIST = re.compile(r'スタッフクレジット|情報整理|日替わり要素|情報一覧|データ一覧')
ANNOUNCEMENT = re.compile(r'お知らせ|発売開始|情報まとめ|企画告知')
ACCOUNT_UPDATE = re.compile(r'note(?:開設|開始).{0,8}周年')
OTHER_TOPIC = re.compile(r'お昼ご飯|今日の献立|電車通勤|セブンカフェ|日々の暮らし|ドラゴンクエストからのお知らせ')
SENSITIVE = re.compile(r'私生活.{0,18}(?:疑惑|裏付け)|事件と本人の心情|メンバーの過去をめぐる示唆')
CURRENT_HOLD = re.compile(r'掲載停止|削除依頼|権利(?:侵害|関係)|プライバシー|管理者確認待ち')
FICTION_CRITIQUE = re.compile(r'(?:妄ツイ|妄リク|夢小説|二次創作).{0,12}(?:文化|批評|規制|是非|倫理)')
INVENTED_RELATION = re.compile(r'(?:一緒に帰る物語を想像|架空の物語|架空のストーリー|創作フィクション)')
GENERIC_SONGS = set(map(norm, (
    'インフルエンサー', 'シンクロニシティ', '歩道橋', '流れ弾', '車間距離', '摩擦係数',
    '承認欲求', '自業自得', 'コインランドリー', '元凶', 'ドライフルーツ', '不協和音',
    '黒い羊', 'BAN', 'Cool', 'Buddies', '僕なんか',
)))


def words(terms):
    keys = sorted({norm(term) for term in terms if term}, key=lambda v: (-len(v), v))
    if not keys:
        return re.compile(r'(?!)')
    return re.compile('|'.join(
        r'(?<![a-z0-9])' + re.escape(key) + r'(?![a-z0-9])'
        if re.fullmatch(r'[a-z0-9]+', key) else re.escape(key)
        for key in keys
    ))


def retained_hold(override):
    if override.get('status') != 'pending':
        return False
    reason = override.get('reason', '')
    if override.get('manual_hold') or SENSITIVE.search(reason) or CURRENT_HOLD.search(reason):
        return True
    # Preserve holds with no migration evidence, including old dashboard holds.
    return not override.get('reviewed_at') and not override.get('review_note')


def instant(value):
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


class Eligibility:
    def __init__(self, rules, previous, overrides):
        config = rules.get('group_rules', {})
        self.subjects = {
            group: words(spec.get('keywords', []) + spec.get('members', []) + spec.get('contexts', []))
            for group, spec in config.items()
        }
        self.aliases = {group: words(spec.get('aliases', [])) for group, spec in config.items()}
        self.songs = {group: words(spec.get('songs', [])) for group, spec in config.items()}
        self.distinct_songs = {
            group: words(song for song in spec.get('songs', []) if norm(song) not in GENERIC_SONGS)
            for group, spec in config.items()
        }
        history = defaultdict(list)
        for row in previous:
            history[row['author_id']].append(row)
        self.profiles = {}
        for author, rows in history.items():
            sample = sorted(rows, key=lambda row: row.get('published_at') or '', reverse=True)[:30]
            evidence = Counter()
            count = 0
            for row in sample:
                editorial = overrides.get(row['url'], {})
                if editorial.get('status') in ('pending', 'excluded'):
                    continue
                groups = self.matches(self.subjects, norm(row['title']))
                if editorial.get('verified_nonfiction') and editorial.get('groups'):
                    groups = editorial['groups']
                if row['status'] == 'published' and groups:
                    evidence.update(groups)
                    count += 1
            if len(sample) < 10:
                self.profiles[author] = ('C', [])
            elif count >= 0.8 * len(sample):
                self.profiles[author] = ('A', [group for group in GROUP_ORDER if evidence[group] >= count * 0.6])
            else:
                self.profiles[author] = ('B', [])

    @staticmethod
    def matches(patterns, value):
        return [group for group in GROUP_ORDER if group in patterns and patterns[group].search(value)]

    def decide(self, title, body, tags, author, editorial, warning):
        t, b = norm(title), norm(body)
        combined = t + ' ' + b
        title_subjects = self.matches(self.subjects, t)
        body_subjects = self.matches(self.subjects, b)
        tag_subjects = self.matches(self.subjects, norm(' '.join(tags)))
        tier, author_groups = self.profiles.get(author, ('C', []))
        title_activity = ACTIVITY.search(t)
        title_topic = TOPIC.search(t)
        body_activity = ACTIVITY.search(b)
        body_topic = TOPIC.search(b)
        if warning and (warning[0] == 'excluded' or not FICTION_CRITIQUE.search(t)):
            return ('excluded' if warning[0] == 'excluded' else 'retry'), 'fiction', []
        if INVENTED_RELATION.search(combined):
            return 'retry', 'fiction', []
        if NOTICE.search(t):
            return 'excluded', 'notice', []
        if (ANNOUNCEMENT.search(t) or REFERENCE_LIST.search(t) or ACCOUNT_UPDATE.search(t)
                or ('自己紹介' in t and not title_activity)) and not body_topic:
            return 'retry' if not body else 'excluded', 'notice', []
        if OTHER_TOPIC.search(t) and not title_subjects:
            return 'excluded', 'other_topic', []
        if creator_focus(title, body):
            return 'published', 'creator', title_subjects
        # A named subject must be tied to an impression or a real activity.
        if title_subjects and (title_topic or title_activity or body_topic or body_activity):
            return 'published', 'title', title_subjects
        song_groups = self.matches(self.distinct_songs, t)
        if song_groups and (title_topic or title_activity or body_topic or body_activity or re.match(r'^[『「].+[』」]――',t)):
            return 'published', 'work', song_groups
        quoted = bool(re.search(r'[『「][^』」]+[』」]', title))
        song_groups = self.matches(self.songs, t)
        corroborated = [g for g in song_groups if g in body_subjects or g in tag_subjects or g in author_groups]
        if quoted and corroborated:
            return 'published', 'work', corroborated
        if not INCIDENTAL.search(b):
            # Tags supply a topic, while the title/feed contributes independent evidence.
            if body_subjects and (body_activity or body_topic or title_activity):
                return 'published', 'feed', title_subjects or body_subjects
            if tag_subjects and (title_activity or (title_topic and body_topic)):
                return 'published', 'tag', title_subjects or tag_subjects
        # The historical editorial evidence identifies a group for this article,
        # but it does not waive explicit creative material or group relevance.
        reviewed_groups = editorial.get('groups', [])
        if reviewed_groups and (FAN_CONTEXT.search(t) or title_activity) and not re.search(r'第\d+話', t):
            return 'published', 'editorial_topic', reviewed_groups
        title_aliases = self.matches(self.aliases, t)
        if (title_activity or FAN_CONTEXT.search(t)) and title_aliases:
            supported = [g for g in title_aliases if g in body_subjects or g in tag_subjects or g in author_groups]
            if supported:
                return 'published', 'alias', supported
        if tier == 'A' and author_groups and FAN_CONTEXT.search(t) and (title_topic or title_activity):
            return 'published', 'author_context', author_groups
        if body and not any((title_subjects, body_subjects, tag_subjects, song_groups, title_aliases, title_activity)):
            return 'excluded', 'other_topic', []
        return 'retry', 'insufficient', []


REASONS = {
    'title': '見出しの坂道の対象と感想・実活動',
    'work': '坂道の作品名と記事の文脈',
    'feed': '公開RSSで確認できる坂道の対象と論評・活動',
    'tag': '配信タグと見出し・配信文の文脈',
    'creator': '制作者・制作活動への論評',
    'editorial_topic': '既存の確認記録と見出しの活動・論評',
    'alias': '坂道の愛称と活動の文脈',
    'author_context': '坂道固有の用語と書き手の掲載傾向',
    'fiction': '創作の明示または創作との区別に必要な情報の不足',
    'notice': '告知・素材登録・広告のみ',
    'other_topic': '取得できた情報では坂道を主題とする記述がない',
    'insufficient': '坂道との関係や記事の種類を確定する情報が不足',
    'date': '元記事の公開日時を確認できない',
    'editorial': '確認済みの掲載判断',
}


def apply(record, eligibility, editorial, previous, now, *, body='', tags=(), warning=None):
    """Apply precedence consistently to a new feed item or a stored retry."""
    status = editorial.get('status')
    title_matches = editorial.get('reviewed_title', record['title']) == record['title']
    if status == 'excluded' or retained_hold(editorial):
        record.update(status=status, reason=editorial.get('reason', '管理者による記事単位の判定'))
        record.pop('retry_until', None)
        return
    if not title_matches:
        editorial = {}
    publication_date = instant(record.get('published_at'))
    if not publication_date or publication_date > now + dt.timedelta(minutes=10):
        verdict, code, groups = 'retry', 'date', []
    elif editorial.get('status') == 'published' and editorial.get('verified_nonfiction'):
        verdict, code, groups = 'published', 'editorial', editorial.get('groups', record.get('groups', []))
    elif previous.get('status') == 'published' and previous.get('title') == record['title']:
        # Previously accepted metadata survives changes to the feed excerpt.
        return
    elif editorial.get('status') == 'published' and not warning:
        verdict, code, groups = 'published', 'editorial', editorial.get('groups', record.get('groups', []))
    else:
        verdict, code, groups = eligibility.decide(record['title'], body, tags, record['author_id'], editorial, warning)
    if verdict == 'published' and not groups and code != 'creator' and CREATOR_CATEGORY not in record.get('categories', []):
        verdict, code = 'retry', 'insufficient'
    if verdict == 'retry':
        deadline = instant(previous.get('retry_until'))
        if not deadline:
            first_seen = instant(record.get('first_seen_at')) or now
            deadline = first_seen + REVIEW_WINDOW
        if now >= deadline:
            verdict = 'unresolved'
            record.pop('retry_until', None)
        else:
            record['retry_until'] = deadline.isoformat()
    else:
        record.pop('retry_until', None)
    record.update(status=verdict, decision_code=code, reason=REASONS.get(code, '管理者による記事単位の判定'))
    if verdict == 'published':
        record['groups'] = groups
