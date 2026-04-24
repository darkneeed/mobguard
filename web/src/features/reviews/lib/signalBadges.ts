type SignalDescriptor = {
  label: string;
  description: string;
};

const REASON_DESCRIPTORS: Record<string, SignalDescriptor> = {
  provider_conflict: {
    label: "Конфликт провайдера",
    description: "Провайдерские признаки противоречат друг другу, автоматическое решение отключено."
  },
  provider_marker_missing: {
    label: "Нет маркера типа сети",
    description: "Провайдер распознан, но нет явного маркера домашнего или мобильного типа."
  },
  provider_review_guardrail: {
    label: "Только вручную",
    description: "Для этого провайдера включён guardrail: решение требует ручной проверки."
  },
  mixed_asn_guarded: {
    label: "ASN смешанного типа",
    description: "ASN известен как смешанный, поэтому одного ASN недостаточно для автоматического решения."
  },
  mixed_asn: {
    label: "ASN смешанного типа",
    description: "ASN имеет смешанный профиль и требует дополнительных подтверждающих признаков."
  },
  pure_home_asn: {
    label: "Домашний ASN",
    description: "ASN относится к домашнему сегменту и усиливает решение в сторону HOME."
  },
  pure_mobile_asn: {
    label: "Мобильный ASN",
    description: "ASN относится к мобильному сегменту и усиливает решение в сторону MOBILE."
  },
  keyword_home: {
    label: "Домашний маркер",
    description: "В названии провайдера или PTR найден домашний ключевой признак."
  },
  keyword_mobile: {
    label: "Мобильный маркер",
    description: "В названии провайдера найден мобильный ключевой признак."
  },
  behavior_churn: {
    label: "Ротация IP",
    description: "Устройство слишком часто меняет IP в коротком окне."
  },
  behavior_history_mobile: {
    label: "История как mobile",
    description: "История IP/подсети этого устройства похожа на мобильный паттерн."
  },
  behavior_history_home: {
    label: "История как home",
    description: "История IP устройства похожа на стабильный домашний паттерн."
  },
  behavior_lifetime: {
    label: "Долгая стабильность",
    description: "Устройство долго держится в одном контексте, что снижает риск мобильного паттерна."
  },
  behavior_subnet_mobile: {
    label: "Мобильная подсеть",
    description: "Подсеть уже накопила мобильные подтверждения."
  },
  behavior_subnet_home: {
    label: "Домашняя подсеть",
    description: "Подсеть уже накопила домашние подтверждения."
  },
  learning_provider: {
    label: "Обучение провайдера",
    description: "Решение поддержано накопленным паттерном по провайдеру."
  },
  learning_provider_service: {
    label: "Обучение сервиса",
    description: "Решение поддержано накопленным паттерном по сервисному типу провайдера."
  },
  learning_asn: {
    label: "Обучение ASN",
    description: "Решение поддержано накопленным паттерном по ASN."
  },
  legacy_learning_asn: {
    label: "Legacy ASN",
    description: "Решение опирается на legacy-learning сигнал по ASN."
  },
  learning_combo: {
    label: "Комбо-паттерн",
    description: "Решение поддержано устойчивой комбинацией признаков."
  },
  ip_api_mobile: {
    label: "Внешний mobile",
    description: "Внешний IP-провайдер подтвердил мобильный профиль."
  },
  manual_override: {
    label: "Ручное правило",
    description: "Для этого IP уже есть ручное правило/override."
  }
};

const SOFT_REASON_DESCRIPTORS: Record<string, SignalDescriptor> = {
  geo_country_jump: {
    label: "Смена страны",
    description: "Устройство за короткое время отметилось в разных странах."
  },
  geo_impossible_travel: {
    label: "Резкое путешествие",
    description: "Одно и то же устройство слишком быстро переместилось между удалёнными локациями."
  },
  device_rotation: {
    label: "Несколько устройств",
    description: "Для этой учётной записи замечено несколько устройств."
  },
  device_os_mismatch: {
    label: "Смена ОС",
    description: "Для одного устройства наблюдаются несовместимые семейства ОС."
  },
  cross_node_fanout: {
    label: "Несколько модулей",
    description: "Одно устройство одновременно проходит через несколько collector-модулей."
  },
  provider_fanout: {
    label: "Много провайдеров",
    description: "Устройство за короткое время ходит через несколько провайдеров."
  },
  traffic_burst: {
    label: "Всплеск трафика",
    description: "Устройство показало подозрительно плотный всплеск активности."
  }
};

const REVIEW_REASON_DESCRIPTORS: Record<string, SignalDescriptor> = {
  provider_conflict: {
    label: "Конфликт провайдера",
    description: "Смешанный провайдер требует ручной проверки до любого действия."
  },
  unsure: {
    label: "Недостаточно сигналов",
    description: "Система не набрала достаточно уверенности для автоматического решения."
  },
  probable_home: {
    label: "Вероятный HOME",
    description: "Кейс выглядит как probable HOME и вынесен в ручную очередь."
  },
  home_requires_review: {
    label: "HOME требует review",
    description: "Получен сильный HOME-вердикт, но guardrail запрещает автоматическое действие."
  },
  manual_review_mixed_home: {
    label: "Mixed HOME review",
    description: "Смешанный HOME-кейс отправлен в ручной разбор."
  }
};

function humanizeCode(code: string): string {
  return code
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function describeReasonCode(code: string): SignalDescriptor {
  return (
    REASON_DESCRIPTORS[code] || {
      label: humanizeCode(code),
      description: `Технический код сигнала: ${code}`
    }
  );
}

export function describeSoftReason(code: string): SignalDescriptor {
  return (
    SOFT_REASON_DESCRIPTORS[code] || {
      label: humanizeCode(code),
      description: `Технический код usage-сигнала: ${code}`
    }
  );
}

export function describeReviewReason(code: string): SignalDescriptor {
  return (
    REVIEW_REASON_DESCRIPTORS[code] || {
      label: humanizeCode(code),
      description: `Технический код причины ревью: ${code}`
    }
  );
}
