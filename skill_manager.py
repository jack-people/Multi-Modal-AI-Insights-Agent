# skill_manager.py
import os
import json
from pathlib import Path
import yaml

class SkillManager:
    def __init__(self):
        # 定位 skills 文件夹
        self.skills_dir = os.path.join(os.path.dirname(__file__), 'skills')
        self.skill_catalog = {}
        self._warnings = []
        self._load_skills()

    @staticmethod
    def _parse_markdown_with_frontmatter(content: str):
        """解析 markdown frontmatter，返回(metadata, sop_text)。"""
        content = content.strip()
        # 兼容两种写法：
        # 1) ---\n<yaml>\n---\n<markdown>
        # 2) <yaml>\n---\n<markdown>
        if content.startswith("---"):
            try:
                _, yaml_text, md_text = content.split("---", 2)
                metadata = yaml.safe_load(yaml_text.strip()) or {}
                return metadata, md_text.strip()
            except Exception:
                # frontmatter 格式不标准时，降级为纯 markdown
                return {}, content
        if "---" in content:
            try:
                yaml_text, md_text = content.split("---", 1)
                metadata = yaml.safe_load(yaml_text.strip()) or {}
                return metadata, md_text.strip()
            except Exception:
                return {}, content
        return {}, content

    def _load_json_config(self, config_path: Path) -> dict:
        if not config_path.exists():
            return {}
        try:
            raw = config_path.read_text(encoding="utf-8").strip()
            if not raw:
                # 空配置文件视为未配置，静默跳过
                return {}
            return json.loads(raw)
        except Exception as e:
            self._warnings.append(f"解析 {config_path} 失败: {e}")
            return {}

    def _load_skills(self):
        """递归解析 skills 下的技能文件（支持 frontmatter 或 config.json）。"""
        if not os.path.exists(self.skills_dir):
            os.makedirs(self.skills_dir)
            return

        for md_path in Path(self.skills_dir).rglob("*.md"):
            try:
                content = md_path.read_text(encoding="utf-8")
            except Exception as e:
                self._warnings.append(f"读取 {md_path} 失败: {e}")
                continue

            frontmatter, sop_text = self._parse_markdown_with_frontmatter(content)
            json_config = self._load_json_config(md_path.parent / "config.json")

            # 优先使用 markdown frontmatter；缺失时回退到同目录 config.json
            metadata = {**json_config, **frontmatter}
            skill_name = metadata.get("name", md_path.stem)
            description = metadata.get("description", "")
            triggers = metadata.get("triggers", [])
            if not isinstance(triggers, list):
                triggers = [str(triggers)]

            self.skill_catalog[skill_name] = {
                "description": description,
                "triggers": triggers,
                "sop": sop_text
            }

        # 单次汇总告警，避免控制台刷屏
        if self._warnings:
            unique_warnings = list(dict.fromkeys(self._warnings))
            print(f"⚠️ SkillManager 发现 {len(unique_warnings)} 个解析告警（仅显示前3条）：")
            for item in unique_warnings[:3]:
                print(f"- {item}")

    def get_all_descriptions(self) -> str:
        """给 Router 生成技能列表"""
        if not self.skill_catalog:
            return "无可用专属技能。"
        desc_list = []
        for name, info in self.skill_catalog.items():
            triggers_str = ", ".join(info['triggers'])
            desc_list.append(f"- 【技能名称: {name}】\n  描述: {info['description']}\n  触发词: {triggers_str}")
        return "\n\n".join(desc_list)

    def get_skill_sop(self, skill_name: str) -> str:
        """给 Executor 提取具体的 Markdown SOP"""
        if skill_name in self.skill_catalog:
            return self.skill_catalog[skill_name]['sop']
        return ""

skill_manager = SkillManager()