-- =============================================================
-- 菏泽市科技博物馆预约与门禁系统 - 数据库初始化脚本 (MySQL 5.7)
-- =============================================================
CREATE DATABASE IF NOT EXISTS heze_museum DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE heze_museum;

-- ---------------------------------------------------------
-- 1. 后台账号表（系统管理员 / 场馆管理员）
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_user (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(50)  NOT NULL UNIQUE COMMENT '登录名',
    password    VARCHAR(128) NOT NULL COMMENT '密码哈希(bcrypt)',
    real_name   VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '姓名',
    role        VARCHAR(20)  NOT NULL DEFAULT 'operator' COMMENT '角色: admin=系统管理员 operator=场馆管理员',
    status      TINYINT      NOT NULL DEFAULT 1 COMMENT '1启用 0禁用',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='后台账号表';

-- ---------------------------------------------------------
-- 2. C端用户表（微信游客，实名信息脱敏存储）
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS wx_user (
    id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    openid         VARCHAR(64)  NOT NULL UNIQUE COMMENT '微信openid',
    unionid        VARCHAR(64)  DEFAULT NULL,
    nickname       VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '昵称',
    real_name      VARCHAR(128) DEFAULT NULL COMMENT '实名姓名(AES+Base64)',
    id_card_no     VARCHAR(128) DEFAULT NULL COMMENT '身份证号哈希索引列',
    id_card_enc    VARCHAR(255) DEFAULT NULL COMMENT '身份证号AES加密Base64存储',
    id_card_masked VARCHAR(20)  DEFAULT NULL COMMENT '脱敏展示: 3729**********1234',
    phone_enc      VARCHAR(255) DEFAULT NULL COMMENT '手机号AES加密Base64存储',
    phone_masked   VARCHAR(20)  DEFAULT NULL COMMENT '脱敏展示: 138****5678',
    is_verified    TINYINT      NOT NULL DEFAULT 0 COMMENT '是否完成实名 0否 1是',
    is_blacklisted TINYINT      NOT NULL DEFAULT 0 COMMENT '黑名单 0否 1是',
    blacklist_reason VARCHAR(200) DEFAULT NULL,
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_idcard (id_card_no(64))
) ENGINE=InnoDB COMMENT='C端微信用户表';

-- ---------------------------------------------------------
-- 3. 场馆配置表（单场馆）
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS venue_info (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) NOT NULL COMMENT '场馆名称',
    address       VARCHAR(200) NOT NULL DEFAULT '' COMMENT '地址',
    open_time     VARCHAR(100) NOT NULL DEFAULT '' COMMENT '开闭馆时间说明',
    traffic_guide TEXT COMMENT '交通指引',
    notice        TEXT COMMENT '入馆须知',
    max_daily     INT UNSIGNED NOT NULL DEFAULT 5000 COMMENT '每日最大承载量',
    status        TINYINT NOT NULL DEFAULT 1 COMMENT '1开放 0闭馆',
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='场馆配置表';

-- ---------------------------------------------------------
-- 4. 预约时段模板表
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS session_slot (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(50) NOT NULL COMMENT '时段名: 上午场/下午场',
    start_time  TIME NOT NULL COMMENT '开始时间',
    end_time    TIME NOT NULL COMMENT '结束时间',
    capacity    INT UNSIGNED NOT NULL COMMENT '该时段最大预约人数',
    is_active   TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用',
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='预约时段模板';

-- ---------------------------------------------------------
-- 5. 展厅/展品表
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS exhibit (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    hall_name     VARCHAR(100) NOT NULL COMMENT '展厅名称',
    title         VARCHAR(100) NOT NULL COMMENT '展品标题',
    description   TEXT COMMENT '图文介绍',
    media_type    VARCHAR(20) NOT NULL DEFAULT 'image' COMMENT 'image/audio/video',
    media_url     VARCHAR(500) DEFAULT NULL COMMENT '媒体地址',
    is_special    TINYINT NOT NULL DEFAULT 0 COMMENT '1=特殊展项(付费可预约体验) 0=普通展项(仅参观浏览)',
    price_cent    INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '体验价格(分), 仅特殊展项有效',
    capacity      INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '每时段可体验人数, 0=不限(普通展项无意义)',
    sort_order    INT NOT NULL DEFAULT 0 COMMENT '排序',
    status        TINYINT NOT NULL DEFAULT 1 COMMENT '1上架 0下架',
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_hall (hall_name)
) ENGINE=InnoDB COMMENT='展厅与展品表';

-- ---------------------------------------------------------
-- 6. 公告表
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS announcement (
    id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title        VARCHAR(100) NOT NULL COMMENT '标题',
    content      TEXT NOT NULL COMMENT '内容',
    type         VARCHAR(20) NOT NULL DEFAULT 'notice' COMMENT 'notice=通知 closure=临时闭馆 activity=活动',
    is_published TINYINT NOT NULL DEFAULT 0 COMMENT '1已发布 0草稿',
    publish_time DATETIME DEFAULT NULL,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_pub (is_published, publish_time)
) ENGINE=InnoDB COMMENT='公告表';

-- ---------------------------------------------------------
-- 7. 预约表（核心）
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS reservation (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    resv_code       CHAR(12) NOT NULL UNIQUE COMMENT '预约码',
    user_id         BIGINT UNSIGNED NOT NULL COMMENT '主预约人 wx_user.id',
    visit_date      DATE NOT NULL COMMENT '参观日期',
    session_id      INT UNSIGNED NOT NULL COMMENT '时段 session_slot.id',
    visitor_count   TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '同行人数(含主预约人)',
    status          VARCHAR(20) NOT NULL DEFAULT 'booked'
                    COMMENT 'booked=已预约 checked_in=已核销(入馆) cancelled=已取消 expired=已过期 no_show=爽约',
    checked_in_at   DATETIME DEFAULT NULL COMMENT '核销时间',
    check_in_gate   VARCHAR(30) DEFAULT NULL COMMENT '核销闸机编号',
    checked_out_at  DATETIME DEFAULT NULL COMMENT '出馆时间',
    cancel_time     DATETIME DEFAULT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_user (user_id, visit_date),
    KEY idx_date (visit_date, session_id, status),
    KEY idx_status (status)
) ENGINE=InnoDB COMMENT='预约表';

-- ---------------------------------------------------------
-- 8. 预约同行人明细表（每个实名游客一行）
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS reservation_visitor (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    reservation_id BIGINT UNSIGNED NOT NULL COMMENT '预约id',
    user_id      BIGINT UNSIGNED DEFAULT NULL COMMENT '关联wx_user.id(注册用户)',
    real_name    VARCHAR(128) NOT NULL COMMENT '姓名(AES+Base64)',
    real_name_masked VARCHAR(64) NOT NULL DEFAULT '' COMMENT '脱敏姓名',
    id_card_no   CHAR(64) NOT NULL COMMENT '身份证号哈希',
    id_card_masked VARCHAR(20) NOT NULL COMMENT '脱敏身份证',
    checked_in   TINYINT NOT NULL DEFAULT 0 COMMENT '该人是否已过闸 0否 1是',
    checked_in_at DATETIME DEFAULT NULL,
    UNIQUE KEY uk_resv_idcard (reservation_id, id_card_no(64)),
    KEY idx_idcard (id_card_no(64))
) ENGINE=InnoDB COMMENT='预约同行人明细';

-- ---------------------------------------------------------
-- 9. 核销记录表（闸机核销流水，幂等核心表）
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS check_record (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    check_type    VARCHAR(20) NOT NULL COMMENT 'qrcode=扫码 idcard=身份证',
    credential    VARCHAR(128) NOT NULL COMMENT '凭证内容: 预约码或身份证号哈希',
    reservation_id BIGINT UNSIGNED DEFAULT NULL COMMENT '命中预约',
    visitor_id    BIGINT UNSIGNED DEFAULT NULL COMMENT '命中预约人明细',
    user_id       BIGINT UNSIGNED DEFAULT NULL,
    direction     VARCHAR(10) NOT NULL DEFAULT 'in' COMMENT 'in=入馆 out=出馆',
    result        VARCHAR(20) NOT NULL COMMENT 'success/fail',
    fail_reason   VARCHAR(100) DEFAULT NULL COMMENT 'invalid_code/already_checked/no_resv/wrong_session/blacklist/capacity_full',
    gate_id       VARCHAR(30) NOT NULL COMMENT '闸机编号',
    device_seq    VARCHAR(64) DEFAULT NULL COMMENT '闸机端指令序号(幂等去重)',
    synced_offline TINYINT NOT NULL DEFAULT 0 COMMENT '是否离线补传 0否 1是',
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_device_seq (gate_id, device_seq),
    KEY idx_resv (reservation_id),
    KEY idx_time (created_at)
) ENGINE=InnoDB COMMENT='核销记录表';

-- ---------------------------------------------------------
-- 10. 通行日志表（对账基准表，闸机开启即记录）
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS access_log (
    id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    reservation_id BIGINT UNSIGNED DEFAULT NULL,
    user_id        BIGINT UNSIGNED DEFAULT NULL,
    visitor_id     BIGINT UNSIGNED DEFAULT NULL,
    gate_id        VARCHAR(30) NOT NULL,
    direction      VARCHAR(10) NOT NULL COMMENT 'in/out',
    pass_time      DATETIME NOT NULL COMMENT '实际过闸时间',
    check_record_id BIGINT UNSIGNED DEFAULT NULL COMMENT '关联核销记录',
    synced_offline TINYINT NOT NULL DEFAULT 0,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_time (pass_time),
    KEY idx_resv (reservation_id)
) ENGINE=InnoDB COMMENT='通行日志表(对账基准)';

-- ---------------------------------------------------------
-- 11. 离线核销补传队列表
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS offline_sync_queue (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    gate_id       VARCHAR(30) NOT NULL,
    device_seq    VARCHAR(64) NOT NULL COMMENT '闸机端本地唯一序号(幂等)',
    payload       JSON NOT NULL COMMENT '原始核销数据',
    status        VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending/done/failed',
    retry_count   INT NOT NULL DEFAULT 0,
    synced_at     DATETIME DEFAULT NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_gate_seq (gate_id, device_seq)
) ENGINE=InnoDB COMMENT='离线核销补传队列';

-- ---------------------------------------------------------
-- 12. 操作日志表（后台审计）
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    admin_id    INT UNSIGNED DEFAULT NULL,
    admin_name  VARCHAR(50) DEFAULT '',
    action      VARCHAR(50) NOT NULL,
    detail      VARCHAR(500) DEFAULT '',
    ip          VARCHAR(50) DEFAULT '',
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_admin (admin_id, created_at)
) ENGINE=InnoDB COMMENT='后台操作审计日志';

-- ---------------------------------------------------------
-- 13. 系统配置表
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_config (
    cfg_key    VARCHAR(50) PRIMARY KEY,
    cfg_value  VARCHAR(500) NOT NULL,
    remark     VARCHAR(200) DEFAULT '',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='系统配置';

-- ---------------------------------------------------------
-- 15. 特殊展项预约表（付费体验; 须先有当日入馆预约）
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS exhibit_reservation (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    resv_code       CHAR(12) NOT NULL UNIQUE COMMENT '展项预约码',
    exhibit_id      INT UNSIGNED NOT NULL COMMENT '展项 exhibit.id',
    user_id         BIGINT UNSIGNED NOT NULL COMMENT '预约人 wx_user.id',
    visit_date      DATE NOT NULL COMMENT '体验日期',
    session_id      INT UNSIGNED NOT NULL COMMENT '体验时段 session_slot.id',
    person_count    TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '体验人数',
    amount_cent     INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '订单金额(分) = 单价×人数',
    pay_status      VARCHAR(20) NOT NULL DEFAULT 'unpaid' COMMENT 'unpaid=待支付 paid=已支付 refunded=已退款',
    paid_at         DATETIME DEFAULT NULL COMMENT '支付时间',
    status          VARCHAR(20) NOT NULL DEFAULT 'booked' COMMENT 'booked=已预约 used=已体验 cancelled=已取消',
    checked_in_count TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '已核验体验人数',
    cancel_time     DATETIME DEFAULT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_user (user_id, visit_date),
    KEY idx_exhibit (exhibit_id, visit_date, session_id, status),
    KEY idx_pay (pay_status)
) ENGINE=InnoDB COMMENT='特殊展项预约表';

-- ---------------------------------------------------------
-- 14. 防刷限制表（同证件同日预约次数控制）
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS resv_daily_limit (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    id_card_no   CHAR(64) NOT NULL COMMENT '身份证哈希',
    visit_date   DATE NOT NULL,
    resv_count   INT NOT NULL DEFAULT 0 COMMENT '当日预约次数(含取消)',
    UNIQUE KEY uk_card_date (id_card_no, visit_date)
) ENGINE=InnoDB COMMENT='证件每日预约次数限制';
